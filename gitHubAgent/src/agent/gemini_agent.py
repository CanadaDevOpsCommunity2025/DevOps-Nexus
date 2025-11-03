"""GeminiChatAgent: lightweight wrapper around Google Generative AI (Gemini) chat model.

Responsibilities:
- Initialize the Gemini model using api key loaded externally.
- Maintain an in-memory conversation history (list of {role, text}).
- Provide generate_reply(user_input) which appends user message, sends to model, stores assistant reply.
- Simple system prompt injection at start.

NOTE: For production, consider persistent storage and user/session separation.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Any
import google.generativeai as genai
import threading

DEFAULT_MODEL_NAME = "gemini-2.5-flash" 
FALLBACK_ORDER = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    "gemini-1.0-pro-latest",
]

class GeminiChatAgent:
    def __init__(self, api_key: str, model_name: str = DEFAULT_MODEL_NAME, system_prompt: Optional[str] = None, max_history: int = 25):
        if not api_key:
            raise ValueError("API key is required for GeminiChatAgent")
        genai.configure(api_key=api_key)
        self.model_name, self.model = self._init_model_with_fallback(model_name)
        self.system_prompt = system_prompt or (
            "You are an helpful AI assistant. Keep responses concise unless asked for detail."
        )
        # store history as list of dicts
        self._history = []  # type: List[Dict[str, str]]
        self._lock = threading.Lock()
        self.max_history = max_history
        # Prepend system message
        if self.system_prompt:
            self._history.append({"role": "system", "text": self.system_prompt})
        # tool registry mapping name->callable
        self._tools: Dict[str, Any] = {}

    def get_history(self) -> List[Dict[str, str]]:
        """Return a shallow copy of the current history."""
        with self._lock:
            return list(self._history)

    def generate_reply(self, user_input: str) -> str:
        if not user_input or not user_input.strip():
            return "Please provide a non-empty message."
        with self._lock:
            self._history.append({"role": "user", "text": user_input})
            # Trim history if exceeds max (keep system + latest pairs)
            if len(self._history) > self.max_history:
                # keep system message if exists
                system = [m for m in self._history if m["role"] == "system"]
                others = [m for m in self._history if m["role"] != "system"]
                # drop oldest from others
                if others:
                    others = others[-(self.max_history - len(system)) :]
                self._history = system + others

            # Prepare messages in format expected by model: list of dicts role/content or simple string chat content.
            # google-generativeai uses "contents"; we can pass entire history as parts.
            # For simplicity, we reconstruct as multiline prompt.
            prompt = self._format_history_for_prompt()
        # Call model outside lock (network IO)
        try:
            response = self.model.generate_content(prompt)
        except Exception as e:
            # Attempt one-time fallback refresh if 404-like error
            if "404" in str(e) or "not found" in str(e).lower():
                try:
                    self.model_name, self.model = self._init_model_with_fallback(self.model_name, force_refresh=True)
                    response = self.model.generate_content(prompt)
                    assistant_text = response.text.strip() if hasattr(response, "text") and response.text else "(No response)"
                except Exception:
                    assistant_text = f"Error from model: {e}"  # original error
            else:
                assistant_text = f"Error from model: {e}"  # don't leak details
        else:
            assistant_text = response.text.strip() if hasattr(response, "text") and response.text else "(No response)"
        with self._lock:
            self._history.append({"role": "assistant", "text": assistant_text})
        return assistant_text

    def _format_history_for_prompt(self) -> str:
        """Convert history into a single prompt string. Basic formatting."""
        lines = []
        for m in self._history:
            prefix = {
                "system": "System",
                "user": "User",
                "assistant": "Assistant"
            }.get(m["role"], m["role"])
            lines.append(f"{prefix}: {m['text']}")
        lines.append("Assistant:")  # cue model
        return "\n".join(lines)

    def _list_models(self) -> List[Dict[str, str]]:
        try:
            models = genai.list_models()
            return [m for m in models]
        except Exception:
            return []

    def _init_model_with_fallback(self, requested: str, force_refresh: bool = False) -> Tuple[str, "genai.GenerativeModel"]:
        """Try requested model; if fails, iterate through FALLBACK_ORDER and then dynamic list."""
        # Try requested first
        try:
            return requested, genai.GenerativeModel(requested)
        except Exception as e:
            if not ("404" in str(e) or "not found" in str(e).lower()):
                # Non-404 error: still propagate by wrapping basic stub
                raise
        # Fallback list (remove duplicates while preserving order)
        tried = {requested}
        for name in FALLBACK_ORDER:
            if name in tried:
                continue
            try:
                return name, genai.GenerativeModel(name)
            except Exception:
                tried.add(name)
                continue
        # Dynamic list as last resort
        for m in self._list_models():
            name = getattr(m, "name", None) or getattr(m, "model", None) or ""
            if not name or name in tried:
                continue
            # Prefer models that include "flash" or "pro" and support generateContent
            info_str = str(m)
            if "generateContent" not in info_str:
                continue
            try:
                return name, genai.GenerativeModel(name)
            except Exception:
                tried.add(name)
                continue
        # Ultimate failure: raise descriptive error
        raise RuntimeError(f"Unable to initialize any Gemini model. Tried: {sorted(tried)}")

    # --- Tool integration methods ---
    def register_tool(self, name: str, func: Any) -> None:
        self._tools[name] = func

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def call_tool(self, name: str, **kwargs) -> Any:
        func = self._tools.get(name)
        if not func:
            raise ValueError(f"Tool '{name}' not registered")
        return func(**kwargs)

# Optional: simple singleton holder (to avoid re-initialization)
_agent_instance: Optional[GeminiChatAgent] = None

def get_agent(api_key: str, model_name: str = DEFAULT_MODEL_NAME) -> GeminiChatAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GeminiChatAgent(api_key=api_key, model_name=model_name)
    return _agent_instance

def reset_agent(api_key: str, model_name: str = DEFAULT_MODEL_NAME) -> GeminiChatAgent:
    """Force re-create the singleton agent with a new model (or same)."""
    global _agent_instance
    _agent_instance = GeminiChatAgent(api_key=api_key, model_name=model_name)
    return _agent_instance
