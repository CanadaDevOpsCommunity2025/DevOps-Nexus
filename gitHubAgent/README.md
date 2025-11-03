# Gemini Chat Agent Web App

A minimal FastAPI + Web UI chat application using Google Gemini API (via `google-generativeai`).

## Features
- FastAPI backend with `/api/chat` endpoint.
- Simple HTML/CSS/JS chat interface.
- In-memory conversation history with system prompt.
- Health endpoint `/api/health`.
- Easy extensibility for streaming or multi-user sessions.

## Prerequisites
- Python 3.12+
- Google AI Studio API key (Gemini) set as environment variable `GEMINI_API_KEY`.

## Setup
1. Create `.env` file:
```
GEMINI_API_KEY=your_key_here
```
2. Install dependencies:
```
python -m pip install -r requirements.txt
```
3. Run development server:
```
python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```
4. Open browser: `http://localhost:8000`

## Tests
Run tests:
```
python -m pytest -q
```

## Project Structure
```
src/
  app.py            # FastAPI application
  agent/
    gemini_agent.py # GeminiChatAgent class
static/
  css/style.css
  js/app.js
templates/
  index.html        # Chat UI
tests/
  test_agent.py     # Unit tests (mocked model)
```

## Extending
- Add user/session separation by keeping a dict of agents keyed by session/user id.
- Add streaming by using `model.stream_generate_content` and Server-Sent Events.
- Persist history to a database (e.g., Redis/PostgreSQL).

## Troubleshooting
- If responses show `Error from model: ...`, verify your API key and model name.
- Ensure firewall allows outbound HTTPS calls to Google endpoints.

## GitHub MCP Server (Optional)
This project includes a simple GitHub Model Context Protocol (MCP) server located at `src/mcp/github_mcp_server.py`.

### Setup
Add to `.env`:
```
GEMINI_API_KEY=your_key_here
GITHUB_TOKEN=ghp_your_token_here
GITHUB_USER=your_github_username   # optional; falls back to token user
```

Install dependencies (PyGithub is required):
```
python -m pip install -r requirements.txt
```

### Run MCP GitHub server
```
python src/mcp/github_mcp_server.py
```
Server listens on port `8001` by default.

### Available Tools
| Tool | Description |
|------|-------------|
| list_repos | List repositories for a user |
| get_repo | Get repository metadata |
| get_file | Fetch file content from a repo |
| search_code | Search code across GitHub (query, language, repo) |
| list_issues | List issues for a repository |
| get_issue | Get a specific issue |
| create_issue | Create a new issue |

### Integrating With Agent
The `GeminiChatAgent` can register tool callables via `register_tool(name, func)` and invoke them with `call_tool(name, **kwargs)`.

Example wiring (pseudo):
```python
from src.agent.gemini_agent import get_agent
from github import Github

agent = get_agent(api_key)
gh = Github(os.getenv("GITHUB_TOKEN"))
def list_my_repos():
  return [r.full_name for r in gh.get_user().get_repos()[:10]]
agent.register_tool("my_repos", lambda: list_my_repos())
```

Then from application logic you can do:
```python
repos = agent.call_tool("my_repos")
```

## GitHub CLI (Alternative to `mcp` Command)
If you attempted commands like `mcp list_repos` and received errors, it's because a standalone `mcp` CLI is not installed here. Instead, use the provided Python CLI:

Run examples (PowerShell):
```powershell
python scripts/github_cli.py list-repos --user youruser
python scripts/github_cli.py get-repo --full-name owner/repo
python scripts/github_cli.py get-file --full-name owner/repo --path README.md
python scripts/github_cli.py search-code --query requests --language python --in-repo owner/repo
python scripts/github_cli.py create-issue --full-name owner/repo --title "Bug" --body "Details" 
```

Requires env var:
```powershell
$env:GITHUB_TOKEN="your_token"
```

Output is JSON; pipe to file or tool as needed:
```powershell
python scripts/github_cli.py list-repos | Out-File repos.json
```

## License
MIT (add a LICENSE file if needed).
