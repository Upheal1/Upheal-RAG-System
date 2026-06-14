"""
Tests for app.runpod_llm_client — all using mocked httpx responses.
Never hits the real RunPod API.
"""

from __future__ import annotations

import os
import importlib
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx


# ---------------------------------------------------------------------------
# Module-scoped env setup for tests that need the module loaded with proper vars
# ---------------------------------------------------------------------------

@pytest.fixture
def configured_env(monkeypatch):
    """Set env vars and reload the runpod_llm_client module."""
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    monkeypatch.setenv("RUNPOD_LLM_ENDPOINT_ID", "gsuqfm5cltizi8")
    monkeypatch.setenv("RUNPOD_LLM_API_BASE", "https://api.runpod.ai/v2")
    monkeypatch.setenv("RUNPOD_LLM_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("RUNPOD_LLM_POLL_INTERVAL_SECONDS", "0.01")
    import app.runpod_llm_client as rlc
    importlib.reload(rlc)
    return rlc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_os_env() -> None:
    """Set env vars directly in os.environ (used by non-fixture config tests)."""
    os.environ["RUNPOD_API_KEY"] = "test-api-key"
    os.environ["RUNPOD_LLM_ENDPOINT_ID"] = "gsuqfm5cltizi8"
    os.environ["RUNPOD_LLM_API_BASE"] = "https://api.runpod.ai/v2"
    os.environ["RUNPOD_LLM_TIMEOUT_SECONDS"] = "30"
    os.environ["RUNPOD_LLM_POLL_INTERVAL_SECONDS"] = "0.01"


def _completed_job(answer: str = "Hello, I'm here to help.") -> dict:
    return {
        "delayTime": 2624,
        "executionTime": 42,
        "id": "job-abc123",
        "output": {"answer": answer, "model": "gemma-3-27b-it-q4_0.gguf"},
        "status": "COMPLETED",
    }


def _make_mock_async_client(
    submit_status: int = 200,
    submit_body: dict | None = None,
    poll_responses: list | None = None,
    submit_side_effect=None,
    poll_side_effect=None,
):
    """Build a mock AsyncClient for httpx.AsyncClient patching.

    Returns a MagicMock whose __aenter__ returns the mock itself,
    with .post and .get bound to the given behaviours.
    """
    if submit_body is None:
        submit_body = {"id": "job-abc123"}
    if poll_responses is None:
        poll_responses = [_completed_job()]

    mock = MagicMock()

    async def _aenter(*a, **kw):
        return mock

    async def _aexit(*a, **kw):
        return None

    mock.__aenter__ = _aenter
    mock.__aexit__ = _aexit

    if submit_side_effect:

        async def submit_fn(url, *args, **kwargs):
            exc = submit_side_effect
            if isinstance(exc, type) and issubclass(exc, BaseException):
                raise exc("submit error")
            raise exc

        mock.post = submit_fn
    else:

        async def _post(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = submit_status
            resp.json.return_value = submit_body
            resp.text = str(submit_body)
            return resp

        mock.post = _post

    if poll_side_effect:

        async def poll_fn(url, *args, **kwargs):
            exc = poll_side_effect
            if isinstance(exc, type) and issubclass(exc, BaseException):
                raise exc("poll error")
            raise exc

        mock.get = poll_fn
    else:

        async def _get(url, *args, **kwargs):
            nonlocal poll_responses
            if not poll_responses:
                body = _completed_job()
            else:
                body = poll_responses.pop(0)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = body
            # For 429 retry-after tests
            resp.headers = MagicMock()
            resp.headers.get.return_value = None
            return resp

        mock.get = _get

    return mock


# ---------------------------------------------------------------------------
# Config validation — test via module reload
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_config_error(monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.setenv("RUNPOD_LLM_ENDPOINT_ID", "x")
    import app.runpod_llm_client as rlc
    importlib.reload(rlc)
    with pytest.raises(rlc.RunPodConfigError, match="RUNPOD_API_KEY"):
        rlc._assert_configured()


def test_missing_endpoint_id_raises_config_error(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.delenv("RUNPOD_LLM_ENDPOINT_ID", raising=False)
    import app.runpod_llm_client as rlc
    importlib.reload(rlc)
    with pytest.raises(rlc.RunPodConfigError, match="RUNPOD_LLM_ENDPOINT_ID"):
        rlc._assert_configured()


# ---------------------------------------------------------------------------
# _extract_answer
# ---------------------------------------------------------------------------

def test_extract_answer_success():
    from app.runpod_llm_client import _extract_answer
    answer = _extract_answer(_completed_job("You matter."))
    assert answer == "You matter."


def test_extract_answer_non_completed():
    from app.runpod_llm_client import _extract_answer, RunPodJobFailedError
    data = {"status": "FAILED", "output": {"answer": "x"}}
    with pytest.raises(RunPodJobFailedError, match="FAILED"):
        _extract_answer(data)


def test_extract_answer_missing_output():
    from app.runpod_llm_client import _extract_answer, RunPodOutputError
    data = {"status": "COMPLETED"}
    with pytest.raises(RunPodOutputError, match="no 'output'"):
        _extract_answer(data)


def test_extract_answer_output_not_dict():
    from app.runpod_llm_client import _extract_answer, RunPodOutputError
    data = {"status": "COMPLETED", "output": "just a string"}
    with pytest.raises(RunPodOutputError, match="not a dict"):
        _extract_answer(data)


def test_extract_answer_missing_answer_key():
    from app.runpod_llm_client import _extract_answer, RunPodOutputError
    data = {"status": "COMPLETED", "output": {"model": "x"}}
    with pytest.raises(RunPodOutputError, match="missing 'answer'"):
        _extract_answer(data)


def test_extract_answer_answer_not_string():
    from app.runpod_llm_client import _extract_answer, RunPodOutputError
    data = {"status": "COMPLETED", "output": {"answer": 42}}
    with pytest.raises(RunPodOutputError, match="not a string"):
        _extract_answer(data)


# ---------------------------------------------------------------------------
# _submit_job
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_submit_success(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client()
    with patch("httpx.AsyncClient", return_value=mock):
        job_id = await rlc._submit_job(
            mock,
            [{"role": "user", "content": "Hi"}],
            0.3,
            220,
        )
    assert job_id == "job-abc123"


@pytest.mark.anyio
async def test_submit_401_raises_auth_error(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_status=401)
    with pytest.raises(rlc.RunPodAuthError):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_429_raises_rate_limit_error(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_status=429)
    with pytest.raises(rlc.RunPodRateLimitError):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_non_200_raises_generic_error(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_status=500)
    with pytest.raises(rlc.RunPodLLMError, match="500"):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_network_timeout(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        submit_side_effect=httpx.TimeoutException("timeout")
    )
    with pytest.raises(rlc.RunPodLLMError, match="Timed out"):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_network_error(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        submit_side_effect=httpx.RequestError("connection refused")
    )
    with pytest.raises(rlc.RunPodLLMError, match="Network error"):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_missing_job_id(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_body={"status": "ok"})
    with pytest.raises(rlc.RunPodLLMError, match="missing job id"):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


@pytest.mark.anyio
async def test_submit_invalid_json(configured_env):
    rlc = configured_env
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    async def _post(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("bad json")
        resp.text = "not json"
        return resp

    mock.post = _post
    with pytest.raises(rlc.RunPodLLMError, match="invalid JSON"):
        await rlc._submit_job(mock, [{"role": "user", "content": "Hi"}], 0.3, 220)


# ---------------------------------------------------------------------------
# _poll_job
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_poll_completed(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[_completed_job("You are heard.")]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "COMPLETED"
    assert data["output"]["answer"] == "You are heard."


@pytest.mark.anyio
async def test_poll_failed(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "FAILED", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "FAILED"


@pytest.mark.anyio
async def test_poll_cancelled(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "CANCELLED", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "CANCELLED"


@pytest.mark.anyio
async def test_poll_timed_out(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "TIMED_OUT", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "TIMED_OUT"


@pytest.mark.anyio
async def test_poll_timeout_exceeded(configured_env, monkeypatch):
    rlc = configured_env
    monkeypatch.setattr(rlc, "RUNPOD_LLM_POLL_INTERVAL_SECONDS", 0.01)

    # Mock asyncio's get_event_loop().time() to return an ever-increasing value
    # so the deadline check triggers quickly.
    t = [0.0]

    def fake_time():
        t[0] += 999.0  # jump well past any reasonable timeout
        return t[0]

    mock_loop = MagicMock()
    mock_loop.time = fake_time
    monkeypatch.setattr(rlc.asyncio, "get_event_loop", lambda: mock_loop)
    monkeypatch.setattr(rlc.asyncio, "sleep", AsyncMock())

    responses = [{"status": "IN_QUEUE"} for _ in range(3)]
    mock = _make_mock_async_client(poll_responses=responses)
    with pytest.raises(rlc.RunPodTimeoutError, match="did not complete"):
        await rlc._poll_job(mock, "job-abc123")


@pytest.mark.anyio
async def test_poll_401_during_polling(configured_env):
    rlc = configured_env
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 401
        return resp

    mock.get = _get
    with pytest.raises(rlc.RunPodAuthError):
        await rlc._poll_job(mock, "job-abc123")


@pytest.mark.anyio
async def test_poll_429_retries(configured_env, monkeypatch):
    rlc = configured_env
    monkeypatch.setenv("RUNPOD_LLM_POLL_INTERVAL_SECONDS", "0.01")
    importlib.reload(rlc)

    call_count = [0]
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, *args, **kwargs):
        call_count[0] += 1
        resp = MagicMock()
        if call_count[0] < 3:
            resp.status_code = 429
            resp.headers.get.return_value = "0.01"
        else:
            resp.status_code = 200
            resp.json.return_value = _completed_job("finally")
        return resp

    mock.get = _get
    data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "COMPLETED"
    assert call_count[0] >= 3


@pytest.mark.anyio
async def test_poll_network_error_retries(configured_env, monkeypatch):
    rlc = configured_env
    monkeypatch.setenv("RUNPOD_LLM_POLL_INTERVAL_SECONDS", "0.01")
    importlib.reload(rlc)

    call_count = [0]
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            raise httpx.RequestError("transient")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _completed_job("recovered")
        return resp

    mock.get = _get
    data = await rlc._poll_job(mock, "job-abc123")
    assert data["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# call_runpod_llm (integration: submit + poll)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_call_runpod_llm_success(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client()
    with patch("httpx.AsyncClient", return_value=mock):
        answer = await rlc.call_runpod_llm(
            [{"role": "user", "content": "I feel sad"}],
            temperature=0.3,
            max_tokens=220,
        )
    assert answer == "Hello, I'm here to help."


@pytest.mark.anyio
async def test_call_runpod_llm_failed_job(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "FAILED", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodJobFailedError, match="FAILED"):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_cancelled_job(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "CANCELLED", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodJobFailedError, match="CANCELLED"):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_timed_out_job(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "TIMED_OUT", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodJobFailedError, match="TIMED_OUT"):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_missing_output_field(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{"status": "COMPLETED", "id": "job-abc123"}]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodOutputError, match="no 'output'"):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_missing_answer_key(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(
        poll_responses=[{
            "status": "COMPLETED",
            "id": "job-abc123",
            "output": {"model": "gemma"},
        }]
    )
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodOutputError, match="missing 'answer'"):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_submit_401(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_status=401)
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodAuthError):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_submit_429(configured_env):
    rlc = configured_env
    mock = _make_mock_async_client(submit_status=429)
    with patch("httpx.AsyncClient", return_value=mock):
        with pytest.raises(rlc.RunPodRateLimitError):
            await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])


@pytest.mark.anyio
async def test_call_runpod_llm_config_missing(configured_env, monkeypatch):
    rlc = configured_env
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    importlib.reload(rlc)
    with pytest.raises(rlc.RunPodConfigError):
        await rlc.call_runpod_llm([{"role": "user", "content": "Hi"}])
