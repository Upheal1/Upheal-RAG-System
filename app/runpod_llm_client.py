"""
RunPod Queue-Based Serverless LLM Client.

Submits a job to the RunPod serverless endpoint, polls for completion,
and returns the model's answer.

Required environment variables:
  RUNPOD_API_KEY
  RUNPOD_LLM_ENDPOINT_ID
  RUNPOD_LLM_API_BASE          (default: https://api.runpod.ai/v2)
  RUNPOD_LLM_TIMEOUT_SECONDS   (default: 600)
  RUNPOD_LLM_POLL_INTERVAL_SECONDS (default: 1.5)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("upheal.runpod_llm")

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
RUNPOD_LLM_ENDPOINT_ID = os.getenv("RUNPOD_LLM_ENDPOINT_ID", "")
RUNPOD_LLM_API_BASE = os.getenv("RUNPOD_LLM_API_BASE", "https://api.runpod.ai/v2")
RUNPOD_LLM_TIMEOUT_SECONDS = int(os.getenv("RUNPOD_LLM_TIMEOUT_SECONDS", "600"))
RUNPOD_LLM_POLL_INTERVAL_SECONDS = float(
    os.getenv("RUNPOD_LLM_POLL_INTERVAL_SECONDS", "1.5")
)

TERMINAL_STATES = frozenset({"COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"})


class RunPodLLMError(Exception):
    """Base error for RunPod LLM client failures."""


class RunPodConfigError(RunPodLLMError):
    """Missing required configuration."""


class RunPodAuthError(RunPodLLMError):
    """Authentication failure (HTTP 401)."""


class RunPodRateLimitError(RunPodLLMError):
    """Rate limited by RunPod (HTTP 429)."""


class RunPodJobFailedError(RunPodLLMError):
    """RunPod job reached a non-COMPLETED terminal state."""


class RunPodTimeoutError(RunPodLLMError):
    """Polling exceeded the configured timeout."""


class RunPodOutputError(RunPodLLMError):
    """COMPLETED job returned malformed or missing output."""


def _assert_configured() -> None:
    """Raise RunPodConfigError if required env vars are missing."""
    if not RUNPOD_API_KEY:
        raise RunPodConfigError("RUNPOD_API_KEY is not set")
    if not RUNPOD_LLM_ENDPOINT_ID:
        raise RunPodConfigError("RUNPOD_LLM_ENDPOINT_ID is not set")


def _auth_headers() -> Dict[str, str]:
    """Return headers without logging the key."""
    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


async def _submit_job(
    client: httpx.AsyncClient,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    """Submit the LLM job and return the job ID."""
    url = f"{RUNPOD_LLM_API_BASE}/{RUNPOD_LLM_ENDPOINT_ID}/run"
    payload: Dict[str, Any] = {
        "input": {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        "policy": {
            "executionTimeout": RUNPOD_LLM_TIMEOUT_SECONDS * 1000,
            "ttl": RUNPOD_LLM_TIMEOUT_SECONDS * 1000,
        },
    }

    try:
        resp = await client.post(url, headers=_auth_headers(), json=payload, timeout=30)
    except httpx.TimeoutException:
        raise RunPodLLMError("Timed out while submitting job to RunPod")
    except httpx.RequestError as exc:
        raise RunPodLLMError(f"Network error submitting job: {exc}")

    if resp.status_code == 401:
        raise RunPodAuthError("RunPod returned 401 — invalid API key")
    if resp.status_code == 429:
        raise RunPodRateLimitError("RunPod rate limit reached (HTTP 429)")
    if resp.status_code != 200:
        body = resp.text[:300]
        raise RunPodLLMError(
            f"RunPod submit returned HTTP {resp.status_code}: {body}"
        )

    try:
        data = resp.json()
    except ValueError:
        raise RunPodLLMError("RunPod submit returned invalid JSON")

    job_id: Optional[str] = data.get("id")
    if not job_id:
        raise RunPodLLMError(f"RunPod submit response missing job id: {data}")
    return job_id


async def _poll_job(
    client: httpx.AsyncClient,
    job_id: str,
) -> Dict[str, Any]:
    """Poll until the job reaches a terminal state and return the full status body."""
    deadline = asyncio.get_event_loop().time() + RUNPOD_LLM_TIMEOUT_SECONDS
    url = f"{RUNPOD_LLM_API_BASE}/{RUNPOD_LLM_ENDPOINT_ID}/status/{job_id}"

    while True:
        if asyncio.get_event_loop().time() > deadline:
            raise RunPodTimeoutError(
                f"RunPod job {job_id} did not complete within "
                f"{RUNPOD_LLM_TIMEOUT_SECONDS}s"
            )

        try:
            resp = await client.get(url, headers=_auth_headers(), timeout=15)
        except httpx.TimeoutException:
            logger.warning("Poll request timed out (job=%s), retrying...", job_id)
            await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)
            continue
        except httpx.RequestError as exc:
            logger.warning("Poll network error (job=%s): %s", job_id, exc)
            await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)
            continue

        if resp.status_code == 401:
            raise RunPodAuthError("RunPod returned 401 while polling — invalid API key")
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", RUNPOD_LLM_POLL_INTERVAL_SECONDS))
            logger.warning("RunPod 429 polling, retrying after %ss", retry_after)
            await asyncio.sleep(retry_after)
            continue
        if resp.status_code != 200:
            logger.warning("Poll HTTP %s (job=%s), retrying...", resp.status_code, job_id)
            await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)
            continue

        try:
            data = resp.json()
        except ValueError:
            logger.warning("Poll returned invalid JSON (job=%s), retrying...", job_id)
            await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)
            continue

        status: Optional[str] = data.get("status")
        if not status:
            logger.warning("Poll response missing status (job=%s): %s", job_id, data)
            await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)
            continue

        if status in TERMINAL_STATES:
            return data

        logger.debug("Job %s status=%s, polling...", job_id, status)
        await asyncio.sleep(RUNPOD_LLM_POLL_INTERVAL_SECONDS)


def _extract_answer(data: Dict[str, Any]) -> str:
    """Extract the answer string from a COMPLETED job status body."""
    status = data.get("status")
    if status != "COMPLETED":
        raise RunPodJobFailedError(
            f"RunPod job finished with status={status} (expected COMPLETED)"
        )

    output: Any = data.get("output")
    if output is None:
        raise RunPodOutputError("RunPod COMPLETED job has no 'output' field")
    if not isinstance(output, dict):
        raise RunPodOutputError(
            f"RunPod output is not a dict, got {type(output).__name__}"
        )

    answer: Optional[str] = output.get("answer")
    if answer is None:
        raise RunPodOutputError("RunPod output dict missing 'answer' key")
    if not isinstance(answer, str):
        raise RunPodOutputError(
            f"RunPod answer is not a string, got {type(answer).__name__}"
        )

    return answer


async def call_runpod_llm(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 220,
) -> str:
    """High-level API: submit job, poll, and return the answer string."""
    _assert_configured()

    logger.info(
        "RunPod LLM submit  messages=%d  temp=%.2f  max_tokens=%d",
        len(messages),
        temperature,
        max_tokens,
    )

    async with httpx.AsyncClient() as client:
        job_id = await _submit_job(client, messages, temperature, max_tokens)
        logger.info("RunPod LLM job submitted: %s", job_id)

        status_data = await _poll_job(client, job_id)
        answer = _extract_answer(status_data)

    logger.info("RunPod LLM answer received  len=%d", len(answer))
    return answer
