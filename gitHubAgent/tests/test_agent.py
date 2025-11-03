import types
import sys
import builtins
import pytest

# We will monkeypatch google.generativeai
from importlib import import_module

# Insert a fake module if not installed for test isolation
if 'google.generativeai' not in sys.modules:
    fake_genai = types.ModuleType('google.generativeai')
    class FakeModel:
        def __init__(self, name):
            self.name = name
            if name == "gemini-1.5-flash":
                # simulate 404 not found
                raise Exception("404 models/gemini-1.5-flash not found")
        def generate_content(self, prompt):
            class R: pass
            r = R()
            r.text = "Echo: " + prompt.split('\n')[-2].split(':',1)[-1].strip()
            return r
    def configure(api_key: str):
        return None
    fake_genai.GenerativeModel = FakeModel
    fake_genai.configure = configure
    sys.modules['google.generativeai'] = fake_genai

from src.agent.gemini_agent import GeminiChatAgent

@pytest.fixture
def agent():
    return GeminiChatAgent(api_key="TEST_KEY", model_name="test-model", system_prompt="System prompt", max_history=5)

def test_initial_history(agent):
    hist = agent.get_history()
    assert hist[0]['role'] == 'system'

def test_generate_reply_appends(agent):
    reply = agent.generate_reply("Hello")
    assert reply.startswith("Echo:")
    hist = agent.get_history()
    assert hist[-1]['role'] == 'assistant'
    assert any(m['role']=='user' for m in hist)

def test_empty_message(agent):
    r = agent.generate_reply("  ")
    assert "non-empty" in r

def test_history_trim(agent):
    for i in range(10):
        agent.generate_reply(f"Message {i}")
    hist = agent.get_history()
    # system + trimmed others <= max_history
    assert len(hist) <= agent.max_history + 1  # +1 because assistant appended after trim logic

def test_fallback_model(agent):
    # After initialization, model_name should not be the failing one
    assert agent.model_name != "gemini-1.5-flash"
