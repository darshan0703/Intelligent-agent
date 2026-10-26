"""
backend/debugging/context_capture.py
Opt-in context capture tool for TheAtom kiosk.

Captures the exact input and metadata sent to LLM invocations during manual
kiosk testing without altering prompt structures or runtime behavior.
"""

import json
import logging
import os
import re
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("context_capture")

# Environment toggle
ENV_VAR_CAPTURE = "LLM_CONTEXT_CAPTURE"
CAPTURES_DIR_NAME = "captures"

# Active capture context for nested tracking (thread-safe and coroutine-safe)
_active_capture_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "_active_capture_context", default=None
)

# Sensitive patterns to redact
_SENSITIVE_PATTERNS = [
    (re.compile(r"gsk_[A-Za-z0-9_\-]{15,}", re.IGNORECASE), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,}", re.IGNORECASE), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"csk\-[A-Za-z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED_CEREBRAS_KEY]"),
    (re.compile(r"sk\-[A-Za-z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\._\-]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
]
_SENSITIVE_KEY_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "secret",
    "password",
    "access_token",
    "auth_token",
    "secret_token",
    "refresh_token",
    "session_token",
    "google_api_key",
    "groq_api_key",
    "cerebras_api_key",
    "openai_api_key",
}

# Tiktoken tokenizer cache for token estimation
_TIKTOKEN_ENCODER = None


def is_capture_enabled() -> bool:
    """Return True if LLM context capture is explicitly enabled via environment variable."""
    return os.getenv(ENV_VAR_CAPTURE, "false").strip().lower() in ("true", "1", "yes")


def get_captures_dir() -> Path:
    """Return the absolute path to the local captures directory, creating it if needed."""
    base_dir = Path(__file__).resolve().parent
    captures_dir = base_dir / CAPTURES_DIR_NAME
    if is_capture_enabled() and not captures_dir.exists():
        try:
            captures_dir.mkdir(parents=True, exist_ok=True)
            # Add a local .gitignore inside captures to prevent committing debug dumps
            gitignore_path = captures_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text("*\n!.gitignore\n", encoding="utf-8")
        except Exception as e:
            logger.warning("Could not create captures directory: %s", e)
    return captures_dir


def scrub_sensitive_data(val: Any) -> Any:
    """Recursively redact API keys, tokens, and credentials from captured objects."""
    if isinstance(val, str):
        cleaned = val
        for pattern, replacement in _SENSITIVE_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned
    elif isinstance(val, dict):
        cleaned_dict = {}
        for k, v in val.items():
            k_lower = str(k).lower().strip()
            # Redact only credential keys, not measurement metrics like prompt_tokens/total_tokens
            is_credential_key = (
                k_lower in _SENSITIVE_KEY_NAMES
                or (
                    (k_lower.endswith("_api_key") or k_lower.endswith("apikey") or k_lower.endswith("_secret") or k_lower.endswith("_token"))
                    and not k_lower.endswith("_tokens")
                )
            )
            if is_credential_key:
                cleaned_dict[k] = "[REDACTED_CREDENTIAL]"
            else:
                cleaned_dict[k] = scrub_sensitive_data(v)
        return cleaned_dict
    elif isinstance(val, (list, tuple)):
        return [scrub_sensitive_data(item) for item in val]
    return val



def get_token_encoder():
    """Lazily load tiktoken encoder for estimating token counts."""
    global _TIKTOKEN_ENCODER
    if _TIKTOKEN_ENCODER is None:
        try:
            import tiktoken
            _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _TIKTOKEN_ENCODER = False
    return _TIKTOKEN_ENCODER if _TIKTOKEN_ENCODER is not False else None


def estimate_tokens(text: Optional[str]) -> int:
    """Estimate token count using tiktoken (cl100k_base) or 4 chars/token heuristic."""
    if not text:
        return 0
    enc = get_token_encoder()
    if enc:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback heuristic
    return max(1, len(text) // 4)


def serialize_tool_definition(tool: Any) -> Dict[str, Any]:
    """Serialize a LangChain tool or tool object into a standard JSON schema representation."""
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool
        return convert_to_openai_tool(tool)
    except Exception:
        # Fallback manual extraction
        name = getattr(tool, "name", str(tool))
        description = getattr(tool, "description", "")
        args = getattr(tool, "args", {})
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": args,
                },
            },
        }


def serialize_message(message: Any, index: int = 0) -> Dict[str, Any]:
    """Serialize a LangChain message preserving full content, role, and tool interactions."""
    msg_type = type(message).__name__
    content = getattr(message, "content", str(message))
    role = "unknown"

    if msg_type == "SystemMessage":
        role = "system"
    elif msg_type == "HumanMessage":
        role = "user"
    elif msg_type == "AIMessage":
        role = "assistant"
    elif msg_type == "ToolMessage":
        role = "tool"

    tool_calls = getattr(message, "tool_calls", None)
    tool_call_id = getattr(message, "tool_call_id", None)
    additional_kwargs = getattr(message, "additional_kwargs", {})
    response_metadata = getattr(message, "response_metadata", {})

    # Extract raw dump if available
    raw_dump = None
    if hasattr(message, "model_dump"):
        try:
            raw_dump = message.model_dump()
        except Exception:
            pass

    return {
        "index": index,
        "role": role,
        "type": msg_type,
        "content": content,
        "tool_calls": tool_calls,
        "tool_call_id": tool_call_id,
        "additional_kwargs": additional_kwargs,
        "response_metadata": response_metadata,
        "raw_dump": raw_dump,
        "estimated_tokens": estimate_tokens(str(content)),
    }


def extract_provider_usage(response: Any) -> Dict[str, Any]:
    """
    Extract provider usage and latency details from model response metadata.
    Marks missing fields explicitly as 'unavailable' rather than estimating.
    """
    metadata = getattr(response, "response_metadata", {}) or {}
    token_usage = metadata.get("token_usage") or {}
    usage_metadata = getattr(response, "usage_metadata", {}) or {}

    def get_field(source_dict, key, default="unavailable"):
        val = source_dict.get(key)
        return val if val is not None else default

    # Token counts
    prompt_tokens = token_usage.get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = usage_metadata.get("input_tokens", "unavailable")

    completion_tokens = token_usage.get("completion_tokens")
    if completion_tokens is None:
        completion_tokens = usage_metadata.get("output_tokens", "unavailable")

    total_tokens = token_usage.get("total_tokens")
    if total_tokens is None:
        total_tokens = usage_metadata.get("total_tokens", "unavailable")

    # Reasoning tokens
    reasoning_tokens = "unavailable"
    comp_details = token_usage.get("completion_tokens_details")
    if isinstance(comp_details, dict) and "reasoning_tokens" in comp_details:
        reasoning_tokens = comp_details["reasoning_tokens"]
    elif isinstance(usage_metadata.get("output_token_details"), dict):
        reasoning_tokens = usage_metadata["output_token_details"].get("reasoning", "unavailable")

    # Latency / timing fields (reported by Groq)
    prompt_time = get_field(token_usage, "prompt_time")
    queue_time = get_field(token_usage, "queue_time")
    completion_time = get_field(token_usage, "completion_time")
    total_time = get_field(token_usage, "total_time")

    system_fingerprint = get_field(metadata, "system_fingerprint")
    finish_reason = get_field(metadata, "finish_reason")

    # Prompt cache tokens (if provider supports it)
    prompt_token_details = "unavailable"
    if "prompt_tokens_details" in token_usage:
        prompt_token_details = token_usage["prompt_tokens_details"] or "unavailable"

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "prompt_time_seconds": prompt_time,
        "queue_time_seconds": queue_time,
        "completion_time_seconds": completion_time,
        "total_time_seconds": total_time,
        "system_fingerprint": system_fingerprint,
        "finish_reason": finish_reason,
        "prompt_token_details": prompt_token_details,
        "raw_response_metadata": scrub_sensitive_data(metadata),
    }


class CaptureSessionManager:
    """Handles writing capture records to JSON files and session JSONL logs."""

    @staticmethod
    def save_capture_record(record: Dict[str, Any]) -> Optional[str]:
        """Save a capture record to disk safely."""
        try:
            captures_dir = get_captures_dir()
            meta = record.get("metadata", {})
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:19]
            interaction_id = meta.get("interaction_id", "unknown_interaction")
            turn_no = meta.get("turn_number", 0)
            call_idx = meta.get("invocation_index", 0)

            filename = f"call_{timestamp_str}_{interaction_id}_t{turn_no}_c{call_idx}.json"
            filepath = captures_dir / filename

            # Clean any sensitive credentials
            clean_record = scrub_sensitive_data(record)

            # Write single-call JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(clean_record, f, indent=2, ensure_ascii=False, default=str)

            # Append to session JSONL
            session_id = meta.get("session_id") or "default_session"
            safe_session_id = re.sub(r"[^A-Za-z0-9_\-]", "_", str(session_id))
            jsonl_path = captures_dir / f"session_{safe_session_id}.jsonl"

            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(clean_record, ensure_ascii=False, default=str) + "\n")


            return str(filepath)
        except Exception as e:
            logger.warning("Failed to save LLM context capture record: %s", e)
            return None


class ActiveCaptureContext:
    """Manages recording of a single LLM invocation."""

    def __init__(
        self,
        messages: Any,
        tools: Optional[List[Any]] = None,
        interaction_id: Optional[str] = None,
        session_id: Optional[str] = None,
        turn_number: int = 1,
        invocation_index: int = 1,
        invocation_type: str = "initial_call",
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        customer_context: Optional[str] = None,
        current_user_input: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.start_wall_time = datetime.now(timezone.utc)
        self.start_perf_time = time.perf_counter()
        self.messages = messages
        self.tools = tools or []
        self.interaction_id = interaction_id
        self.session_id = session_id
        self.turn_number = turn_number
        self.invocation_index = invocation_index
        self.invocation_type = invocation_type
        self.model_name = model_name or "openai/gpt-oss-20b"
        self.system_prompt = system_prompt
        self.customer_context = customer_context
        self.current_user_input = current_user_input
        self.extra_metadata = extra_metadata or {}
        self.token = None
        self.saved_path = None

    def __enter__(self):
        self.token = _active_capture_context.set({
            "interaction_id": self.interaction_id,
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "invocation_index": self.invocation_index,
        })
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            _active_capture_context.reset(self.token)

    def record_response(self, response: Any, actual_provider: Optional[str] = None):
        """Called immediately after LLM execution to package and persist the capture."""
        try:
            elapsed_seconds = time.perf_counter() - self.start_perf_time

            # 1. Serialize messages
            serialized_messages = []
            if isinstance(self.messages, list):
                for idx, msg in enumerate(self.messages):
                    serialized_messages.append(serialize_message(msg, idx))
            elif isinstance(self.messages, str):
                serialized_messages.append({
                    "index": 0,
                    "role": "user",
                    "type": "PromptString",
                    "content": self.messages,
                    "estimated_tokens": estimate_tokens(self.messages),
                })

            # 2. Serialize tools
            serialized_tools = [serialize_tool_definition(t) for t in self.tools]

            # 3. Extract system prompt and customer context from messages if not passed
            sys_prompt = self.system_prompt
            cust_context = self.customer_context
            current_user_msg = self.current_user_input

            if not sys_prompt and isinstance(self.messages, list):
                for m in self.messages:
                    if getattr(m, "type", None) == "system" or type(m).__name__ == "SystemMessage":
                        content = getattr(m, "content", "")
                        if "CURRENT CUSTOMER CONTEXT:" in content:
                            if not cust_context:
                                cust_context = content
                        elif not sys_prompt:
                            sys_prompt = content

            if not current_user_msg and isinstance(self.messages, list):
                for m in reversed(self.messages):
                    if getattr(m, "type", None) == "human" or type(m).__name__ == "HumanMessage":
                        current_user_msg = getattr(m, "content", "")
                        break

            # 4. Extract provider usage
            provider_usage = extract_provider_usage(response)

            # 5. Extract response details
            resp_content = getattr(response, "content", str(response))
            resp_tool_calls = getattr(response, "tool_calls", None)
            resp_additional_kwargs = getattr(response, "additional_kwargs", {})

            # 6. Build structured record
            record = {
                "capture_id": f"cap_{self.start_wall_time.strftime('%Y%m%d_%H%M%S_%f')}",
                "timestamp_utc": self.start_wall_time.isoformat(),
                "metadata": {
                    "interaction_id": self.interaction_id or "unavailable",
                    "session_id": self.session_id or "unavailable",
                    "turn_number": self.turn_number,
                    "invocation_index": self.invocation_index,
                    "invocation_type": self.invocation_type,
                    "model_name": self.model_name,
                    "provider": actual_provider or "groq",
                    "elapsed_time_seconds": round(elapsed_seconds, 4),
                    **self.extra_metadata,
                },
                "context_breakdown": {
                    "system_instructions": {
                        "system_prompt": sys_prompt,
                        "customer_context": cust_context,
                        "system_prompt_estimated_tokens": estimate_tokens(sys_prompt),
                        "customer_context_estimated_tokens": estimate_tokens(cust_context),
                    },
                    "current_turn": {
                        "user_input": current_user_msg,
                        "user_input_estimated_tokens": estimate_tokens(current_user_msg),
                    },
                    "conversation_history_messages": serialized_messages,
                    "tool_definitions": serialized_tools,
                    "tool_definitions_count": len(serialized_tools),
                    "total_messages_count": len(serialized_messages),
                    "total_estimated_prompt_tokens": sum(m.get("estimated_tokens", 0) for m in serialized_messages),
                },
                "raw_model_input": {
                    "format": "langchain_messages" if isinstance(self.messages, list) else "prompt_string",
                    "messages": serialized_messages,
                    "tools": serialized_tools,
                },
                "model_response": {
                    "content": resp_content,
                    "tool_calls": resp_tool_calls,
                    "additional_kwargs": scrub_sensitive_data(resp_additional_kwargs),
                },
                "provider_usage": provider_usage,
            }

            self.saved_path = CaptureSessionManager.save_capture_record(record)
        except Exception as e:
            logger.warning("Error recording LLM context capture: %s", e)


class DummyCaptureContext:
    """No-op context manager when capture is disabled."""
    saved_path = None
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def record_response(self, response: Any, actual_provider: Optional[str] = None):
        pass


def capture_llm_call(
    messages: Any,
    tools: Optional[List[Any]] = None,
    interaction_id: Optional[str] = None,
    session_id: Optional[str] = None,
    turn_number: int = 1,
    invocation_index: int = 1,
    invocation_type: str = "initial_call",
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    customer_context: Optional[str] = None,
    current_user_input: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager to wrap an LLM invocation.
    If LLM_CONTEXT_CAPTURE is not enabled, returns a no-op dummy immediately.
    """
    if not is_capture_enabled():
        return DummyCaptureContext()

    try:
        # Try retrieving interaction_id from perf tracer if not explicitly passed
        if not interaction_id:
            try:
                from perf import get_current_tracer
                tracer = get_current_tracer()
                if tracer:
                    interaction_id = getattr(tracer, "interaction_id", None)
            except Exception:
                pass

        return ActiveCaptureContext(
            messages=messages,
            tools=tools,
            interaction_id=interaction_id,
            session_id=session_id,
            turn_number=turn_number,
            invocation_index=invocation_index,
            invocation_type=invocation_type,
            model_name=model_name,
            system_prompt=system_prompt,
            customer_context=customer_context,
            current_user_input=current_user_input,
            extra_metadata=extra_metadata,
        )
    except Exception as e:
        logger.warning("Failed to initialize capture context: %s", e)
        return DummyCaptureContext()


def capture_standalone_call(
    prompt_or_messages: Any,
    response: Any,
    tools: Optional[List[Any]] = None,
    model_name: Optional[str] = None,
    interaction_id: Optional[str] = None,
    session_id: Optional[str] = None,
    call_type: str = "standalone_invoke",
    provider: str = "groq",
    duration_seconds: float = 0.0,
):
    """
    Captures an LLM invocation made outside AgentRuntime (e.g., fallback process_message or direct invoke).
    No-op if capture is disabled or if an active capture context is already tracking this call.
    """
    if not is_capture_enabled():
        return None

    # If this call is already nested inside an ActiveCaptureContext, do not duplicate!
    if _active_capture_context.get() is not None:
        return None

    try:
        if not interaction_id:
            try:
                from perf import get_current_tracer
                tracer = get_current_tracer()
                if tracer:
                    interaction_id = getattr(tracer, "interaction_id", None)
            except Exception:
                pass

        ctx = ActiveCaptureContext(
            messages=prompt_or_messages,
            tools=tools or [],
            interaction_id=interaction_id,
            session_id=session_id,
            turn_number=0,
            invocation_index=1,
            invocation_type=call_type,
            model_name=model_name,
        )
        ctx.start_perf_time = time.perf_counter() - duration_seconds
        ctx.record_response(response, actual_provider=provider)
        return ctx.saved_path
    except Exception as e:
        logger.warning("Error in capture_standalone_call: %s", e)
        return None


class CapturingLLMProxy:
    """Wraps an LLM instance to capture direct invocations outside AgentRuntime."""

    def __init__(self, llm: Any, model_name: Optional[str] = None):
        self._llm = llm
        self._model_name = (
            model_name
            or getattr(llm, "model_name", None)
            or getattr(llm, "model", None)
            or "openai/gpt-oss-20b"
        )

    def invoke(self, input_data: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        response = self._llm.invoke(input_data, **kwargs)
        duration = time.perf_counter() - t0
        try:
            interaction_id = None
            try:
                from perf import get_current_tracer
                tracer = get_current_tracer()
                if tracer:
                    interaction_id = getattr(tracer, "interaction_id", None)
            except Exception:
                pass

            capture_standalone_call(
                prompt_or_messages=input_data,
                response=response,
                model_name=str(self._model_name),
                interaction_id=interaction_id,
                duration_seconds=duration,
            )
        except Exception as e:
            logger.warning("Error in CapturingLLMProxy: %s", e)
        return response

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        bound = self._llm.bind_tools(tools, **kwargs)
        return CapturingLLMProxy(bound, model_name=self._model_name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)


def wrap_llm_for_capture(llm: Any, model_name: Optional[str] = None) -> Any:
    """Wrap an LLM instance with a capturing proxy if capture is enabled. Returns llm untouched otherwise."""
    if not is_capture_enabled() or llm is None:
        return llm
    return CapturingLLMProxy(llm, model_name=model_name)

