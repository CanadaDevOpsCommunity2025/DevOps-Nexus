from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import re
import google.generativeai as genai
import json

from src.agent.gemini_agent import get_agent, reset_agent, DEFAULT_MODEL_NAME
from src.agent.gemini_agent import GeminiChatAgent
try:
    # Import underlying GitHub tool functions (prefix underscore). Safe even if token absent.
    from src.mcp.github_mcp_server import (
        _list_repos,
        _get_repo,
        _get_file,
        _search_code,
        _list_issues,
        _get_issue,
        _create_issue,
        _cherry_pick,
    )
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_OVERRIDE = os.getenv("GEMINI_MODEL")
if not API_KEY:
    # We'll allow app to start but warn later in responses.
    print("WARNING: GEMINI_API_KEY not set. Set in .env or environment.")

app = FastAPI(title="Gemini Chat Agent")

# Mount static assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

def _register_github_tools(agent: GeminiChatAgent):
    if not GITHUB_AVAILABLE:
        return
    # Wrap raw functions to provide clearer namespaced tool set
    agent.register_tool("github.list_repos", lambda user=None: _list_repos(user))
    agent.register_tool("github.get_repo", lambda full_name: _get_repo(full_name))
    agent.register_tool("github.get_file", lambda full_name, path, ref=None: _get_file(full_name, path, ref))
    agent.register_tool("github.search_code", lambda query, language=None, in_repo=None: _search_code(query, language, in_repo))
    agent.register_tool("github.list_issues", lambda full_name, state="open": _list_issues(full_name, state))
    agent.register_tool("github.get_issue", lambda full_name, number: _get_issue(full_name, number))
    agent.register_tool("github.create_issue", lambda full_name, title, body: _create_issue(full_name, title, body))
    agent.register_tool("github.cherry_pick", lambda repository, targetBranch, prFilterQuery, callbackUrl=None: _cherry_pick(repository, targetBranch, prFilterQuery, callbackUrl))

COMMAND_PREFIXES = ("/tool", "/github", "!tool", "!github")

def parse_tool_command(message: str):
    """Parse a tool invocation command.
    Expected forms:
      /tool github.list_repos user=foo
      !github github.search_code query=auth language=python in_repo=owner/repo
    Returns (tool_name, args_dict) or (None, {})."""
    if not message:
        return None, {}
    msg = message.strip()
    # Quick prefix detection
    if not any(msg.startswith(p) for p in COMMAND_PREFIXES):
        return None, {}
    # Remove leading prefix
    parts = msg.split()
    if len(parts) < 2:
        return None, {}
    # first token is prefix, second is tool name
    tool_name = parts[1].strip()
    arg_tokens = parts[2:]
    args = {}
    for tok in arg_tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            args[k] = v
    return tool_name, args

@app.on_event("startup")
async def startup_register_tools():
    if API_KEY:
        agent = get_agent(API_KEY, model_name=MODEL_OVERRIDE or DEFAULT_MODEL_NAME)
        _register_github_tools(agent)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "model_name": DEFAULT_MODEL_NAME})

@app.post("/api/chat")
async def chat(request: Request):
    if not API_KEY:
        return JSONResponse({"error": "Server missing GEMINI_API_KEY."}, status_code=500)
    data = await request.json()
    message = data.get("message", "")
    agent = get_agent(API_KEY, model_name=MODEL_OVERRIDE or DEFAULT_MODEL_NAME)
    # Check for tool command
    tool_name, tool_args = parse_tool_command(message)
    if tool_name:
        if tool_name in agent.list_tools():
            try:
                result = agent.call_tool(tool_name, **tool_args)
                # Serialize the result into reply text
                if isinstance(result, (str, int, float)):
                    result_text = str(result)
                else:
                    try:
                        result_text = json.dumps(result, ensure_ascii=False, indent=2)
                    except Exception:
                        result_text = str(result)
                # Optionally truncate overly large payloads
                max_len = 8000
                if len(result_text) > max_len:
                    result_text = result_text[:max_len] + "\n... (truncated)"
                reply_text = f"[tool:{tool_name}]\n{result_text}"
                agent._history.append({"role": "assistant", "text": reply_text})
                return JSONResponse({
                    "reply": reply_text,
                    "tool_result": result,
                    "history": agent.get_history()
                })
            except Exception as e:
                error_text = f"[tool:{tool_name}] error: {e}"
                agent._history.append({"role": "assistant", "text": error_text})
                return JSONResponse({
                    "reply": error_text,
                    "history": agent.get_history()
                }, status_code=500)
        else:
            # Unknown tool; fall back to model response noting tool unrecognized.
            message = f"User asked for unknown tool '{tool_name}'. Original: {message}"
    reply = agent.generate_reply(message)
    return JSONResponse({"reply": reply, "history": agent.get_history()})

@app.post("/api/model")
async def change_model(request: Request):
    """Change the active Gemini model at runtime. Body: {"model_name": "gemini-..."}"""
    if not API_KEY:
        return JSONResponse({"error": "Server missing GEMINI_API_KEY."}, status_code=500)
    data = await request.json()
    new_name = data.get("model_name")
    if not new_name:
        return JSONResponse({"error": "model_name required"}, status_code=400)
    try:
        agent = reset_agent(API_KEY, model_name=new_name)
        return {"ok": True, "model": agent.model_name}
    except Exception as e:
        # Keep old agent if failure
        return JSONResponse({"error": f"Failed to switch model: {e}"}, status_code=500)

@app.get("/api/health")
async def health():
    return {"status": "ok", "has_api_key": bool(API_KEY), "model": MODEL_OVERRIDE or DEFAULT_MODEL_NAME}

@app.get("/api/models")
async def list_models():
    if not API_KEY:
        return JSONResponse({"error": "Missing API key"}, status_code=500)
    genai.configure(api_key=API_KEY)
    try:
        models = genai.list_models()
        items = []
        for m in models:
            name = getattr(m, "name", None) or getattr(m, "model", None)
            items.append({
                "name": name,
                "raw": str(m)
            })
        return {"models": items}
    except Exception as e:
        return JSONResponse({"error": f"Failed to list models: {e}"}, status_code=500)

@app.get("/api/tools")
async def list_tools():
    if not API_KEY:
        return {"tools": []}
    agent = get_agent(API_KEY, model_name=MODEL_OVERRIDE or DEFAULT_MODEL_NAME)
    return {"tools": agent.list_tools()}

# Entrypoint for uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)
