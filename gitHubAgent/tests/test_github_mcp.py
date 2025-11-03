import types, sys
import pytest

# Mock PyGithub components minimally
class FakeRepo:
    def __init__(self, name):
        self.name = name
        self.full_name = f"user/{name}"
        self.private = False
        self.description = "Desc"
        self.stargazers_count = 5
        self.forks_count = 2
        self.open_issues_count = 1
        self.default_branch = "main"
        self._issues = [FakeIssue(1, "Issue title")]
    def get_repos(self):
        return [self]
    def get_contents(self, path, ref=None):
        return types.SimpleNamespace(path=path, decoded_content=b"content", size=7)
    def get_issues(self, state="open"):
        return self._issues
    def get_issue(self, number):
        return self._issues[0]
    def create_issue(self, title, body):
        return types.SimpleNamespace(number=2, html_url="http://example/issue/2")

class FakeIssue:
    def __init__(self, number, title):
        self.number = number
        self.title = title
        self.state = "open"
        self.body = "Body"
        self.user = types.SimpleNamespace(login="user")
        self.comments = 0

class FakeUser:
    def __init__(self):
        self.login = "user"
    def get_repos(self):
        return [FakeRepo("repo")]        

class FakeGithub:
    def __init__(self, token):
        self.token = token
    def get_user(self, user=None):
        return FakeUser()
    def get_repo(self, full_name):
        return FakeRepo(full_name.split('/')[-1])
    def search_code(self, q):
        r = types.SimpleNamespace(name="file.py", path="file.py", repository=types.SimpleNamespace(full_name="user/repo"), html_url="http://example/file")
        return [r]

sys.modules['github'] = types.ModuleType('github')
sys.modules['github'].Github = FakeGithub

from src.mcp.github_mcp_server import _list_repos, _get_repo, _get_file, _search_code, _list_issues, _get_issue, _create_issue

# Monkeypatch get_client to return fake github
import src.mcp.github_mcp_server as server_mod
server_mod.get_client = lambda : FakeGithub("token")


def test_list_repos():
    repos = _list_repos("user")
    assert repos and repos[0]['full_name'].startswith('user/')

def test_get_repo():
    info = _get_repo("user/repo")
    assert info['stars'] == 5

def test_get_file():
    fc = _get_file("user/repo", "path/to/file.txt")
    assert fc['decoded_content'] == 'content'

def test_search_code():
    res = _search_code("print", language="python", in_repo="user/repo")
    assert res[0]['path'] == 'file.py'

def test_issue_flow():
    issues = _list_issues("user/repo")
    assert issues[0]['number'] == 1
    issue = _get_issue("user/repo", 1)
    assert issue['title'] == 'Issue title'
    created = _create_issue("user/repo", "New", "Body")
    assert created['created'] is True
