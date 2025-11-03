"""GitHub MCP Server

Implements a simple Model Context Protocol server exposing GitHub operations as tools.
Tools:
- list_repos(user?)
- get_repo(full_name)
- get_file(full_name, path, ref?)
- search_code(query, language?, in_repo?)
- list_issues(full_name, state?)
- get_issue(full_name, number)
- create_issue(full_name, title, body)

This is a lightweight illustrative implementation; not production-hardened.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, APIRouter
from github import Github

# Attempt to import MCP library. If unavailable, degrade to simple FastAPI tool endpoints.
MCP_AVAILABLE = True
try:
    from mcp.server.fastapi import FastAPIContextServer  # type: ignore
    from mcp.server import Server  # type: ignore
    from mcp.shared.messages import Tool  # type: ignore
except Exception:
    MCP_AVAILABLE = False

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEFAULT_USER = os.getenv("GITHUB_USER", "")

def ensure_environment():
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is missing. Set it via environment or .env file. "
            "Windows PowerShell (session): $env:GITHUB_TOKEN='ghp_xxx' | Persistent: [System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN','ghp_xxx','User')"
        )
    return True

# Initialize GitHub client lazily

def get_client() -> Github:
    ensure_environment()
    return Github(GITHUB_TOKEN)

# Tool implementations

def _list_repos(user: Optional[str] = None) -> List[Dict[str, Any]]:
    gh = get_client()
    user = user or DEFAULT_USER or gh.get_user().login
    u = gh.get_user(user)
    return [{
        "name": r.name,
        "full_name": r.full_name,
        "private": r.private,
        "description": r.description,
    } for r in u.get_repos()]

def _get_repo(full_name: str) -> Dict[str, Any]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    return {
        "full_name": repo.full_name,
        "description": repo.description,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "default_branch": repo.default_branch,
    }

def _get_file(full_name: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    file_content = repo.get_contents(path, ref=ref) if ref else repo.get_contents(path)
    return {
        "path": file_content.path,
        "decoded_content": file_content.decoded_content.decode("utf-8", errors="replace"),
        "size": file_content.size,
    }

def _search_code(query: str, language: Optional[str] = None, in_repo: Optional[str] = None) -> List[Dict[str, Any]]:
    gh = get_client()
    terms = [query]
    if language:
        terms.append(f"language:{language}")
    if in_repo:
        terms.append(f"repo:{in_repo}")
    q = " ".join(terms)
    results = gh.search_code(q)
    out = []
    for r in results[:25]:  # limit
        out.append({
            "name": r.name,
            "path": r.path,
            "repository": r.repository.full_name,
            "url": r.html_url,
        })
    return out

def _list_issues(full_name: str, state: str = "open") -> List[Dict[str, Any]]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    return [{
        "number": i.number,
        "title": i.title,
        "state": i.state,
        "user": i.user.login,
        "comments": i.comments,
    } for i in repo.get_issues(state=state)]

def _get_issue(full_name: str, number: int) -> Dict[str, Any]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    issue = repo.get_issue(number)
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "body": issue.body,
        "user": issue.user.login,
    }

def _create_issue(full_name: str, title: str, body: str) -> Dict[str, Any]:
    gh = get_client()
    repo = gh.get_repo(full_name)
    issue = repo.create_issue(title=title, body=body)
    return {"created": True, "number": issue.number, "url": issue.html_url}

def _cherry_pick(repo_full_name: str, target_branch: str, pr_filter_query: str, callback_url: Optional[str] = None) -> Dict[str, Any]:
    """Plan a cherry-pick operation by enumerating commits from PRs matching a filter query.

    NOTE: This does not perform git-level cherry-picks (requires a local clone and push). Instead it returns
    a structured plan including unique commit SHAs that could be cherry-picked onto the target branch.

    Parameters:
      repo_full_name: owner/repo string.
      target_branch: branch name to cherry-pick onto.
      pr_filter_query: GitHub search qualifiers excluding repo/type (those are auto-added). Example: "is:closed label:backport".
      callback_url: optional URL to POST the result plan (not executed here for safety; future enhancement).
    """
    gh = get_client()
    repo = gh.get_repo(repo_full_name)
    # Build search query: restrict to repo and pull requests
    search_q = f"repo:{repo_full_name} {pr_filter_query} type:pr"
    issues = gh.search_issues_and_pull_requests(search_q)
    pull_data: List[Dict[str, Any]] = []
    seen_commits: Set[str] = set()
    for issue in issues[:20]:  # limit for safety
        try:
            pr_number = issue.number
            pr = repo.get_pull(pr_number)
            commits = []
            for c in pr.get_commits():
                commits.append({"sha": c.sha, "message": c.commit.message.split("\n")[0]})
                seen_commits.add(c.sha)
            pull_data.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "head_ref": pr.head.ref,
                "base_ref": pr.base.ref,
                "mergeable": pr.mergeable,
                "commits": commits,
            })
        except Exception:
            continue
    plan = {
        "repository": repo_full_name,
        "target_branch": target_branch,
        "query": pr_filter_query,
        "pull_request_count": len(pull_data),
        "pull_requests": pull_data,
        "unique_commit_count": len(seen_commits),
        "commit_shas": list(seen_commits),
        "action": "analysis_only",
        "message": "Cherry-pick plan generated; no commits applied. Use a local git workflow to perform actual cherry-picks.",
    }
    return plan

# Build MCP server using FastAPI adapter

def build_server() -> FastAPI:
    if MCP_AVAILABLE:
        server = Server("github-mcp")
        server.add_tool(Tool(name="list_repos", description="List repositories for a user", input_schema={"type": "object", "properties": {"user": {"type": "string"}}}))
        server.add_tool(Tool(name="get_repo", description="Get repository details", input_schema={"type": "object", "required": ["full_name"], "properties": {"full_name": {"type": "string"}}}))
        server.add_tool(Tool(name="get_file", description="Retrieve file content", input_schema={"type": "object", "required": ["full_name", "path"], "properties": {"full_name": {"type": "string"}, "path": {"type": "string"}, "ref": {"type": "string"}}}))
        server.add_tool(Tool(name="search_code", description="Search code across GitHub", input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "language": {"type": "string"}, "in_repo": {"type": "string"}}}))
        server.add_tool(Tool(name="list_issues", description="List issues in a repository", input_schema={"type": "object", "required": ["full_name"], "properties": {"full_name": {"type": "string"}, "state": {"type": "string"}}}))
        server.add_tool(Tool(name="get_issue", description="Get a specific issue", input_schema={"type": "object", "required": ["full_name", "number"], "properties": {"full_name": {"type": "string"}, "number": {"type": "number"}}}))
        server.add_tool(Tool(name="create_issue", description="Create an issue", input_schema={"type": "object", "required": ["full_name", "title", "body"], "properties": {"full_name": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}}))
        server.add_tool(Tool(name="cherry-pick", description="Cherry-pick commits from PRs based on a filter query to a target branch (analysis only)", input_schema={"type": "object", "required": ["repository", "targetBranch", "prFilterQuery"], "properties": {"repository": {"type": "string"}, "targetBranch": {"type": "string"}, "prFilterQuery": {"type": "string"}, "callbackUrl": {"type": "string"}}}))

        @server.call_tool("list_repos")
        async def call_list_repos(arguments: Dict[str, Any]):
            return _list_repos(arguments.get("user"))

        @server.call_tool("get_repo")
        async def call_get_repo(arguments: Dict[str, Any]):
            return _get_repo(arguments["full_name"])

        @server.call_tool("get_file")
        async def call_get_file(arguments: Dict[str, Any]):
            return _get_file(arguments["full_name"], arguments["path"], arguments.get("ref"))

        @server.call_tool("search_code")
        async def call_search_code(arguments: Dict[str, Any]):
            return _search_code(arguments["query"], arguments.get("language"), arguments.get("in_repo"))

        @server.call_tool("list_issues")
        async def call_list_issues(arguments: Dict[str, Any]):
            return _list_issues(arguments["full_name"], arguments.get("state", "open"))

        @server.call_tool("get_issue")
        async def call_get_issue(arguments: Dict[str, Any]):
            return _get_issue(arguments["full_name"], int(arguments["number"]))

        @server.call_tool("create_issue")
        async def call_create_issue(arguments: Dict[str, Any]):
            return _create_issue(arguments["full_name"], arguments["title"], arguments["body"])

        @server.call_tool("cherry-pick")
        async def call_cherry_pick(arguments: Dict[str, Any]):
            return _cherry_pick(arguments["repository"], arguments["targetBranch"], arguments["prFilterQuery"], arguments.get("callbackUrl"))

        return FastAPIContextServer(server).fastapi_app
    # Fallback simple FastAPI implementation
    app = FastAPI(title="github-mcp-fallback")
    router = APIRouter(prefix="/tool")
    TOOL_META: Dict[str, Dict[str, Any]] = {
        "list_repos": {"description": "List repositories for a user", "params": ["user"]},
        "get_repo": {"description": "Get repository details", "params": ["full_name"]},
        "get_file": {"description": "Retrieve file content", "params": ["full_name", "path", "ref?"]},
        "search_code": {"description": "Search code across GitHub", "params": ["query", "language?", "in_repo?"]},
        "list_issues": {"description": "List issues in a repository", "params": ["full_name", "state?"]},
        "get_issue": {"description": "Get a specific issue", "params": ["full_name", "number"]},
        "create_issue": {"description": "Create an issue", "params": ["full_name", "title", "body"]},
        "cherry-pick": {"description": "Cherry-pick commit plan from matching PRs (analysis only)", "params": ["repository", "targetBranch", "prFilterQuery", "callbackUrl?"]},
    }

    @app.get("/tools")
    async def tools():
        return {"mcp": False, "tools": TOOL_META}

    @router.post("/list_repos")
    async def t_list_repos(payload: Dict[str, Any]):
        return _list_repos(payload.get("user"))

    @router.post("/get_repo")
    async def t_get_repo(payload: Dict[str, Any]):
        return _get_repo(payload["full_name"])

    @router.post("/get_file")
    async def t_get_file(payload: Dict[str, Any]):
        return _get_file(payload["full_name"], payload["path"], payload.get("ref"))

    @router.post("/search_code")
    async def t_search_code(payload: Dict[str, Any]):
        return _search_code(payload["query"], payload.get("language"), payload.get("in_repo"))

    @router.post("/list_issues")
    async def t_list_issues(payload: Dict[str, Any]):
        return _list_issues(payload["full_name"], payload.get("state", "open"))

    @router.post("/get_issue")
    async def t_get_issue(payload: Dict[str, Any]):
        return _get_issue(payload["full_name"], int(payload["number"]))

    @router.post("/create_issue")
    async def t_create_issue(payload: Dict[str, Any]):
        return _create_issue(payload["full_name"], payload["title"], payload["body"])

    @router.post("/cherry-pick")
    async def t_cherry_pick(payload: Dict[str, Any]):
        return _cherry_pick(payload["repository"], payload["targetBranch"], payload["prFilterQuery"], payload.get("callbackUrl"))

    app.include_router(router)
    return app

if __name__ == "__main__":
    import uvicorn
    app = build_server()
    uvicorn.run(app, host="127.0.0.1", port=8001)
