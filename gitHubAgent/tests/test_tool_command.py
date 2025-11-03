import pytest
from src.app import parse_tool_command

@pytest.mark.parametrize("msg,expected_tool", [
    ("/tool github.list_repos user=foo", "github.list_repos"),
    ("!github github.search_code query=auth language=python in_repo=owner/repo", "github.search_code"),
    ("/tool github.get_repo full_name=owner/repo", "github.get_repo"),
    ("plain text", None),
])
def test_parse_tool_command(msg, expected_tool):
    tool, args = parse_tool_command(msg)
    assert tool == expected_tool
    if expected_tool:
        # Ensure args parsed when present
        if "user=foo" in msg:
            assert args.get("user") == "foo"
        if "full_name=owner/repo" in msg:
            assert args.get("full_name") == "owner/repo"
        if "query=auth" in msg:
            assert args.get("query") == "auth"

