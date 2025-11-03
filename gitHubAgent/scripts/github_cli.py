"""Lightweight GitHub tools CLI.

Usage examples:
    python scripts/github_cli.py list-repos --user someuser
    python scripts/github_cli.py get-repo --full-name owner/repo
    python scripts/github_cli.py get-file --full-name owner/repo --path README.md
    python scripts/github_cli.py search-code --query requests --language python --in-repo owner/repo
    python scripts/github_cli.py create-issue --full-name owner/repo --title "Bug" --body "Details"

Requires environment variable GITHUB_TOKEN (and optional GITHUB_USER default).
Falls back with a clear error if token missing.
"""
from __future__ import annotations
import os
import sys
import json
import argparse
from typing import Any

try:
    from github import Github  # type: ignore
except Exception:
    print("PyGithub not installed. Install with: python -m pip install PyGithub", file=sys.stderr)
    sys.exit(1)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USER = os.getenv("GITHUB_USER")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN not set in environment.", file=sys.stderr)
    sys.exit(2)

gh = Github(GITHUB_TOKEN)

# --- Command implementations ---

def cmd_list_repos(args: argparse.Namespace) -> Any:
    user = args.user or GITHUB_USER or gh.get_user().login
    u = gh.get_user(user)
    data = [{
        "name": r.name,
        "full_name": r.full_name,
        "private": r.private,
        "description": r.description,
    } for r in u.get_repos()]
    return data

def cmd_get_repo(args: argparse.Namespace) -> Any:
    repo = gh.get_repo(args.full_name)
    return {
        "full_name": repo.full_name,
        "description": repo.description,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "default_branch": repo.default_branch,
    }

def cmd_get_file(args: argparse.Namespace) -> Any:
    repo = gh.get_repo(args.full_name)
    fc = repo.get_contents(args.path, ref=args.ref) if args.ref else repo.get_contents(args.path)
    return {"path": fc.path, "size": fc.size, "content": fc.decoded_content.decode("utf-8", errors="replace")}

def cmd_search_code(args: argparse.Namespace) -> Any:
    terms = [args.query]
    if args.language:
        terms.append(f"language:{args.language}")
    if args.in_repo:
        terms.append(f"repo:{args.in_repo}")
    q = " ".join(terms)
    results = gh.search_code(q)
    out = []
    for r in results[: args.limit]:
        out.append({"name": r.name, "path": r.path, "repo": r.repository.full_name, "url": r.html_url})
    return out

def cmd_list_issues(args: argparse.Namespace) -> Any:
    repo = gh.get_repo(args.full_name)
    return [{"number": i.number, "title": i.title, "state": i.state, "user": i.user.login} for i in repo.get_issues(state=args.state)]

def cmd_get_issue(args: argparse.Namespace) -> Any:
    repo = gh.get_repo(args.full_name)
    issue = repo.get_issue(args.number)
    return {"number": issue.number, "title": issue.title, "state": issue.state, "body": issue.body}

def cmd_create_issue(args: argparse.Namespace) -> Any:
    repo = gh.get_repo(args.full_name)
    issue = repo.create_issue(title=args.title, body=args.body)
    return {"created": True, "number": issue.number, "url": issue.html_url}

# --- Main parser ---

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GitHub Tools CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list-repos", help="List repositories")
    sp.add_argument("--user", help="GitHub username override")
    sp.set_defaults(func=cmd_list_repos)

    sp = sub.add_parser("get-repo", help="Get repo metadata")
    sp.add_argument("--full-name", required=True)
    sp.set_defaults(func=cmd_get_repo)

    sp = sub.add_parser("get-file", help="Get file contents")
    sp.add_argument("--full-name", required=True)
    sp.add_argument("--path", required=True)
    sp.add_argument("--ref")
    sp.set_defaults(func=cmd_get_file)

    sp = sub.add_parser("search-code", help="Search code")
    sp.add_argument("--query", required=True)
    sp.add_argument("--language")
    sp.add_argument("--in-repo")
    sp.add_argument("--limit", type=int, default=10)
    sp.set_defaults(func=cmd_search_code)

    sp = sub.add_parser("list-issues", help="List issues")
    sp.add_argument("--full-name", required=True)
    sp.add_argument("--state", default="open")
    sp.set_defaults(func=cmd_list_issues)

    sp = sub.add_parser("get-issue", help="Get issue details")
    sp.add_argument("--full-name", required=True)
    sp.add_argument("--number", type=int, required=True)
    sp.set_defaults(func=cmd_get_issue)

    sp = sub.add_parser("create-issue", help="Create issue")
    sp.add_argument("--full-name", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--body", required=True)
    sp.set_defaults(func=cmd_create_issue)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
