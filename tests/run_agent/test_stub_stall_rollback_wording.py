"""Regression tests for diaria-studio#6847 -- stub-stall rollback wording.

The two "rollback" return points inside run_conversation's
``finish_reason == "length"`` handling (agent/conversation_loop.py, reached
when the truncated response falls through both the text-continuation branch
and the tool-call-retry branch -- i.e. the response could not be normalized
into an assistant message at all) used to report
"Response truncated due to output length limit" unconditionally, even when
the underlying cause was a partial-stream stub (upstream SSE dropped mid-
flight -- a network failure, not the model hitting its output cap).

This pins:

- with response.id == PARTIAL_STREAM_STUB_ID, both rollback branches (prior
  messages present / first message ever) report the network-drop wording
  and never mention "output length limit".
- without the stub id, the legacy "output length limit" wording is
  unchanged -- the fix must not regress the real-truncation case.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hermes_constants import PARTIAL_STREAM_STUB_ID


def _make_unnormalizable_length_response(response_id: str):
    """A finish_reason='length' response whose id is under test.

    Paired with ``_force_unnormalizable`` below, this specific response
    object normalizes to None, which is what pushes execution past both the
    text-continuation and tool-call-retry branches straight into the
    rollback section (agent/conversation_loop.py, ~4069-4121) -- the two
    branches both require a non-None normalized assistant message, so a
    None short-circuits into the fallback rollback path unconditionally.
    """
    msg = SimpleNamespace(content="partial", tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason="length")
    return SimpleNamespace(
        choices=[choice], model="test/model", usage=None, id=response_id,
    )


@pytest.fixture()
def loop_agent():
    """AIAgent with a mocked OpenAI client (mirrors
    test_partial_stream_finish_reason.py's ``loop_agent`` fixture)."""
    from run_agent import AIAgent
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        a._cached_system_prompt = "You are helpful."
        a._use_prompt_caching = False
        a.compression_enabled = False
        a.save_trajectories = False
        return a


def _force_unnormalizable(agent, target_response):
    """Make the real chat_completions transport return None from its
    SECOND ``normalize_response`` call for ``target_response`` -- every
    other response, and the FIRST call for ``target_response`` itself,
    still normalize normally through the real transport.

    The finish_reason=="length" handling normalizes the same response
    object twice: once early (agent/conversation_loop.py ~3568, to derive
    ``finish_reason`` -- this must keep working normally, or the API-call
    wrapper crashes before ever reaching the code under test) and once
    again inside the length-handling block itself (~3707-3715, building
    ``_trunc_msg``). Returning None only from the SECOND call reproduces
    the exact "response could not be normalized into an assistant message"
    condition that pushes execution past both the text-continuation and
    tool-call-retry branches into the rollback section (~4069-4121),
    without faking the rest of the transport (preflight_kwargs and friends
    stay real).
    """
    transport = agent._get_transport("chat_completions")
    original_normalize = transport.normalize_response
    call_counts: dict = {}

    def _wrapped(response, **kwargs):
        if response is target_response:
            call_counts[id(response)] = call_counts.get(id(response), 0) + 1
            if call_counts[id(response)] >= 2:
                return None
        return original_normalize(response, **kwargs)

    transport.normalize_response = _wrapped


class TestStubStallRollbackReportsNetworkDrop:
    """response.id == PARTIAL_STREAM_STUB_ID must never surface the
    'output length limit' wording out of the rollback branches
    (diaria-studio#6847)."""

    def test_rollback_with_prior_messages_uses_network_wording(self, loop_agent):
        stub = _make_unnormalizable_length_response(PARTIAL_STREAM_STUB_ID)
        _force_unnormalizable(loop_agent, stub)
        loop_agent.client.chat.completions.create.return_value = stub

        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]

        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            result = loop_agent.run_conversation(
                "second question", conversation_history=history,
            )

        assert result["completed"] is False
        assert result["partial"] is True
        assert "output length limit" not in (result["final_response"] or "")
        assert "output length limit" not in (result["error"] or "")
        assert "Stream dropped before completion (network)" in result["final_response"], (
            "Stub-stall rollback (with prior messages) must report the "
            "network-drop wording, not the output-length-limit lie "
            "(diaria-studio#6847)."
        )
        assert "Stream dropped before completion (network)" in result["error"]

    def test_rollback_first_message_uses_network_wording(self, loop_agent):
        stub = _make_unnormalizable_length_response(PARTIAL_STREAM_STUB_ID)
        _force_unnormalizable(loop_agent, stub)
        loop_agent.client.chat.completions.create.return_value = stub

        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            result = loop_agent.run_conversation("first ever question")

        assert result["completed"] is False
        assert result["failed"] is True
        assert "output length limit" not in (result["final_response"] or "")
        assert "output length limit" not in (result["error"] or "")
        assert "First response dropped before completion (network)" in result["final_response"], (
            "Stub-stall rollback (first message ever) must report the "
            "network-drop wording, not the output-length-limit lie "
            "(diaria-studio#6847)."
        )
        assert "First response dropped before completion (network)" in result["error"]


class TestLegitTruncationRollbackWordingUnchanged:
    """Without the stub id, the pre-existing 'output length limit' wording
    must still be reported -- the fix must not regress the real-truncation
    case (diaria-studio#6847)."""

    def test_rollback_with_prior_messages_keeps_length_wording(self, loop_agent):
        real_truncation = _make_unnormalizable_length_response("resp-real-truncation-1")
        _force_unnormalizable(loop_agent, real_truncation)
        loop_agent.client.chat.completions.create.return_value = real_truncation

        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]

        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            result = loop_agent.run_conversation(
                "second question", conversation_history=history,
            )

        assert result["final_response"] == "Response truncated due to output length limit"
        assert result["error"] == "Response truncated due to output length limit"

    def test_rollback_first_message_keeps_length_wording(self, loop_agent):
        real_truncation = _make_unnormalizable_length_response("resp-real-truncation-2")
        _force_unnormalizable(loop_agent, real_truncation)
        loop_agent.client.chat.completions.create.return_value = real_truncation

        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            result = loop_agent.run_conversation("first ever question")

        assert result["final_response"] == "First response truncated due to output length limit"
        assert result["error"] == "First response truncated due to output length limit"
