import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from langchain_core.messages import AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from debugging.context_capture import capture_standalone_call


# ==============================================================================
# Environment Configuration
# ==============================================================================
_backend_dir = Path(__file__).resolve().parent.parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file)
else:
    load_dotenv()

# ==============================================================================
# Model Constants
# ==============================================================================
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "qwen-3.8-27b")
CEREBRAS_API_BASE = os.getenv("CEREBRAS_API_BASE", "https://api.cerebras.ai/v1")
CEREBRAS_TIMEOUT = float(os.getenv("CEREBRAS_TIMEOUT", "10.0"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "5.0"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

logger = logging.getLogger("model")


def is_transient_error(exc: Exception) -> bool:
    """
    Identifies retryable/transient errors such as rate limits (HTTP 429),
    temporary server issues (HTTP 5xx), timeouts, and connection interruptions.
    Permanent client errors (e.g. 400 Bad Request, 401 Invalid Auth, 404 Not Found)
    return False.
    """
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)

    # Permanent client errors: fail-fast, do not retry on fallback
    if status_code in (400, 401, 403, 404):
        return False

    err_str = str(exc).lower()
    if any(term in err_str for term in [
        "invalid api key",
        "unauthorized",
        "invalid_argument",
        "bad request",
        "model not found",
        "not found",
    ]):
        return False

    # Retryable transient errors
    if status_code in (429, 500, 502, 503, 504):
        return True

    if any(term in err_str for term in [
        "rate limit",
        "429",
        "quota",
        "resource_exhausted",
        "resourceexhausted",
        "tokens",
        "tpm",
        "rpm",
        "timeout",
        "timed out",
        "connection error",
        "connection",
        "service unavailable",
        "overloaded",
    ]):
        return True

    return False


def sanitize_messages_for_gemini(messages: Any) -> Any:
    """
    Transforms LangChain messages containing tool calls and tool execution results
    into conversational history suitable for Gemini.

    Google's Gemini API enforces a strict cryptographic thought_signature check
    on any raw functionCall parts in history. When falling back from Groq (or when
    cross-provider tool calls are passed), raw functionCall parts trigger an
    HTTP 400 'missing a thought_signature' error.

    This function converts tool executions and tool responses into descriptive context
    while preserving 100% of execution results (screens, selections, meal offers)
    and conversation validity.
    """
    if not isinstance(messages, list):
        return messages

    sanitized = []
    i = 0
    n = len(messages)

    while i < n:
        msg = messages[i]

        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tool_calls = msg.tool_calls
            tool_call_ids = {tc.get("id"): tc for tc in tool_calls if tc.get("id")}

            results = []
            j = i + 1
            while j < n and isinstance(messages[j], ToolMessage):
                tool_msg = messages[j]
                tc_id = getattr(tool_msg, "tool_call_id", None)
                tc = tool_call_ids.get(tc_id)
                tool_name = tc.get("name") if tc else getattr(tool_msg, "name", "tool")
                tool_args = tc.get("args") if tc else {}
                results.append(
                    f"Action executed: {tool_name}({tool_args})\nResult: {tool_msg.content}"
                )
                j += 1

            action_summary = "\n".join(f"[{res}]" for res in results)
            if not action_summary and tool_calls:
                calls_str = ", ".join(f"{tc.get('name')}({tc.get('args')})" for tc in tool_calls)
                action_summary = f"[Action requested: {calls_str}]"

            base_content = msg.content if isinstance(msg.content, str) and msg.content else ""
            if base_content and action_summary:
                combined_content = f"{base_content}\n{action_summary}"
            elif action_summary:
                combined_content = action_summary
            else:
                combined_content = base_content or ""

            if j < n and isinstance(messages[j], AIMessage) and not getattr(messages[j], "tool_calls", None):
                followup_content = messages[j].content or ""
                if followup_content:
                    combined_content = f"{combined_content}\n{followup_content}".strip()
                j += 1

            sanitized.append(AIMessage(content=combined_content))
            i = j
            continue

        elif isinstance(msg, ToolMessage):
            sanitized.append(AIMessage(content=f"[Tool result: {msg.content}]"))
            i += 1
            continue

        else:
            sanitized.append(msg)
            i += 1

    return sanitized


class FallbackToolBinding:
    """
    Wraps model tool binding to provide Gemini fallback on retryable Groq errors.
    """

    def __init__(self, tools: Any, parent: "ModelAdapter", **kwargs: Any):
        self.tools = tools
        self.parent = parent
        self.kwargs = kwargs

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        combined_kwargs = {**self.kwargs, **kwargs}
        return self.parent._invoke_with_fallback(
            messages,
            tools=self.tools,
            **combined_kwargs,
        )


class ModelAdapter:
    """
    LLM model adapter:
    - Primary provider: Cerebras (CEREBRAS_API_KEY) with qwen-3.8-27b
    - Fallback provider: Google Gemini (GEMINI_API_KEY) on transient/rate-limit failures
    - Supports both direct invoke and tool binding
    """

    def __init__(self):
        self.cerebras_key = (os.getenv("CEREBRAS_API_KEY") or "").strip()
        self.gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.groq_key = (os.getenv("GROQ_API_KEY") or "").strip()

        if not self.cerebras_key:
            raise ValueError("CEREBRAS_API_KEY is not set in environment or .env file.")

        self.primary_model = ChatOpenAI(
            model=CEREBRAS_MODEL,
            temperature=0,
            max_retries=0,
            timeout=CEREBRAS_TIMEOUT,
            api_key=self.cerebras_key,
            base_url=CEREBRAS_API_BASE,
        )

    @property
    def model_name(self) -> str:
        return getattr(self.primary_model, "model_name", CEREBRAS_MODEL)

    def bind_tools(self, tools: Any, **kwargs: Any) -> FallbackToolBinding:
        """Binds tools with automatic Gemini fallback on transient failures."""
        return FallbackToolBinding(tools, self, **kwargs)

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        """Invokes the primary model with automatic Gemini fallback on transient failures."""
        return self._invoke_with_fallback(messages, tools=None, **kwargs)

    def _invoke_with_fallback(self, messages: Any, tools: Optional[Any] = None, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        # 1. Attempt using primary provider (Cerebras)
        try:
            if tools:
                resp = self.primary_model.bind_tools(tools, **kwargs).invoke(messages)
            else:
                resp = self.primary_model.invoke(messages, **kwargs)
            duration = time.perf_counter() - t0
            capture_standalone_call(
                prompt_or_messages=messages,
                response=resp,
                tools=tools,
                model_name=CEREBRAS_MODEL,
                provider="cerebras",
                duration_seconds=duration,
            )
            return resp
        except Exception as cerebras_exc:
            # 2. Check if the error is an eligible transient failure
            if not is_transient_error(cerebras_exc):
                raise cerebras_exc

            logger.warning(
                "Cerebras encountered transient error (%s). Falling back to Gemini...",
                type(cerebras_exc).__name__,
            )

            # Check fallback key availability
            gemini_key = self.gemini_key or (os.getenv("GEMINI_API_KEY") or "").strip()
            if not gemini_key:
                raise RuntimeError(
                    f"Cerebras failed with transient error: {cerebras_exc}. "
                    "Cannot fall back to Gemini because GEMINI_API_KEY is not configured."
                ) from cerebras_exc

            # 3. Attempt request using fallback provider (Gemini)
            try:
                fallback_model = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    temperature=0,
                    google_api_key=gemini_key,
                    transport="rest",
                    timeout=GEMINI_TIMEOUT,
                    max_retries=0,
                )
                # Suppress hidden ResourceExhausted time.sleep backoff in langchain_google_genai
                orig_generate = getattr(getattr(fallback_model, "client", None), "generate_content", None)
                if callable(orig_generate):
                    def _fail_fast_generate(*args: Any, **kwargs: Any) -> Any:
                        try:
                            return orig_generate(*args, **kwargs)
                        except ResourceExhausted as exc:
                            if hasattr(exc, "retry_after"):
                                try:
                                    del exc.retry_after
                                except (AttributeError, TypeError):
                                    exc.retry_after = 0
                            raise
                    fallback_model.client.generate_content = _fail_fast_generate

                gemini_messages = sanitize_messages_for_gemini(messages)
                if tools:
                    resp = fallback_model.bind_tools(tools, **kwargs).invoke(gemini_messages)
                else:
                    resp = fallback_model.invoke(gemini_messages, **kwargs)
                duration = time.perf_counter() - t0
                capture_standalone_call(
                    prompt_or_messages=gemini_messages,
                    response=resp,
                    tools=tools,
                    model_name=GEMINI_MODEL,
                    provider="gemini",
                    duration_seconds=duration,
                )
                return resp
            except Exception as gemini_exc:
                # 4. If fallback also fails, raise meaningful error
                raise RuntimeError(
                    f"Primary provider (Cerebras) failed with transient error: {cerebras_exc}. "
                    f"Fallback provider (Gemini) also failed: {gemini_exc}."
                ) from gemini_exc

    def __getattr__(self, name: str) -> Any:
        return getattr(self.primary_model, name)


class GroqModel(ModelAdapter):
    """Backward compatibility alias for ModelAdapter."""
    pass


# Export singleton instance for existing callers
model = ModelAdapter()