"""
Unit and regression tests for LLM latency, bounded timeouts, and fallback behavior.
Verifies:
1. Primary provider (Cerebras) timeout triggers automatic fallback to Gemini.
2. Fallback execution returns expected assistant response without duplicate tool execution.
3. Provider attempt durations and total operation duration are tracked and recorded.
4. Non-transient client errors fail-fast without calling fallback.
5. Dual provider failure raises structured RuntimeError with attempt timings.
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from services.model import ModelAdapter, is_transient_error


def test_is_transient_error_classification():
    """Verify transient vs non-transient error classification."""
    # Transient errors
    assert is_transient_error(Exception("Connection timed out after 3.5s")) is True
    assert is_transient_error(Exception("Rate limit exceeded 429")) is True
    assert is_transient_error(Exception("503 Service Unavailable")) is True

    # Non-transient client errors
    assert is_transient_error(Exception("401 Unauthorized: Invalid API key")) is False
    assert is_transient_error(Exception("400 Bad Request: Invalid model")) is False
    assert is_transient_error(Exception("404 Model not found")) is False


def test_primary_timeout_triggers_gemini_fallback():
    """Verify primary provider timeout triggers reliable Gemini fallback."""
    adapter = ModelAdapter()
    messages = [HumanMessage(content="Hello")]

    mock_gemini_response = AIMessage(content="Hello from Gemini fallback!")

    # Simulate primary model timing out
    with patch("langchain_openai.ChatOpenAI.invoke", side_effect=Exception("Timeout connecting to Cerebras after 3.5s")):
        with patch("services.model.ChatGoogleGenerativeAI") as MockGemini:
            mock_gemini_instance = MagicMock()
            mock_gemini_instance.invoke.return_value = mock_gemini_response
            MockGemini.return_value = mock_gemini_instance

            resp = adapter.invoke(messages)
            assert resp.content == "Hello from Gemini fallback!"
            mock_gemini_instance.invoke.assert_called_once()


def test_primary_non_transient_error_fails_fast():
    """Verify non-transient client errors fail-fast without calling fallback."""
    adapter = ModelAdapter()
    messages = [HumanMessage(content="Hello")]

    with patch("langchain_openai.ChatOpenAI.invoke", side_effect=Exception("401 Unauthorized: Invalid API Key")):
        with patch("services.model.ChatGoogleGenerativeAI") as MockGemini:
            with pytest.raises(Exception) as exc_info:
                adapter.invoke(messages)

            assert "401 Unauthorized" in str(exc_info.value)
            MockGemini.assert_not_called()


def test_dual_provider_failure_raises_timing_error():
    """Verify that when both primary and fallback fail, a structured error with timings is raised."""
    adapter = ModelAdapter()
    messages = [HumanMessage(content="Hello")]

    with patch("langchain_openai.ChatOpenAI.invoke", side_effect=Exception("Cerebras connection timed out")):
        with patch("services.model.ChatGoogleGenerativeAI") as MockGemini:
            mock_gemini_instance = MagicMock()
            mock_gemini_instance.invoke.side_effect = Exception("Gemini service unavailable 503")
            MockGemini.return_value = mock_gemini_instance

            with pytest.raises(RuntimeError) as exc_info:
                adapter.invoke(messages)

            err_msg = str(exc_info.value)
            assert "Primary provider (Cerebras) failed" in err_msg
            assert "Fallback provider (Gemini) also failed" in err_msg
            assert "Total duration:" in err_msg


def test_attempt_timing_recorded_in_perf_tracer():
    """Verify primary attempt, fallback attempt, and total durations are logged to PerfTracer."""
    adapter = ModelAdapter()
    messages = [HumanMessage(content="Hello")]

    mock_tracer = MagicMock()
    mock_gemini_response = AIMessage(content="Fallback response")

    with patch("services.model.get_current_tracer", return_value=mock_tracer):
        with patch("langchain_openai.ChatOpenAI.invoke", side_effect=Exception("Cerebras timeout")):
            with patch("services.model.ChatGoogleGenerativeAI") as MockGemini:
                mock_gemini_instance = MagicMock()
                mock_gemini_instance.invoke.return_value = mock_gemini_response
                MockGemini.return_value = mock_gemini_instance

                adapter.invoke(messages)

                # Check tracer log calls
                logged_events = [call[0][0] for call in mock_tracer.log.call_args_list]
                assert "llm_primary_attempt" in logged_events
                assert "llm_fallback_attempt" in logged_events
                assert "llm_operation_completed" in logged_events
