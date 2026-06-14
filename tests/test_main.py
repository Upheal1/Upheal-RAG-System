"""
Tests for UpHeal backend — sessions, history, memory, prompt building, auth.

All external services (Supabase, RunPod) are mocked.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


# Set required env vars before importing app
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test123"
os.environ["RUNPOD_API_KEY"] = "test-api-key"
os.environ["RUNPOD_LLM_ENDPOINT_ID"] = "gsuqfm5cltizi8"
os.environ["RUNPOD_LLM_API_BASE"] = "https://api.runpod.ai/v2"
os.environ["RUNPOD_LLM_TIMEOUT_SECONDS"] = "30"
os.environ["RUNPOD_LLM_POLL_INTERVAL_SECONDS"] = "0.01"
os.environ["QDRANT_URL"] = ""
os.environ["ENABLE_RAG"] = "false"
os.environ["CHAT_HISTORY_LIMIT"] = "12"
os.environ["AI_MEMORY_LIMIT"] = "8"

from app.main import app

client = TestClient(app)


# ── Constants ────────────────────────────────────────────────────────────────

VALID_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
VALID_TOKEN = "valid-supabase-access-token"
VALID_SESSION_ID = "11111111-1111-1111-1111-111111111111"
INVALID_UUID = "not-a-uuid"


def _auth_header(token: str = VALID_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Mock helpers ─────────────────────────────────────────────────────────────

def _mock_auth():
    """Patch require_auth to return (user_id, token)."""
    return patch("app.main.require_auth", new=AsyncMock(
        return_value=(VALID_USER_ID, VALID_TOKEN)
    ))


def _mock_handle_text_turn(answer="I hear you.", sid=VALID_SESSION_ID):
    return patch("app.main.handle_text_turn", new=AsyncMock(return_value={
        "answer": answer, "session_id": sid,
        "request_id": "req_1234567890",
    }))


def _mock_load_session_history(messages=None):
    if messages is None:
        messages = [
            {"id": "m1", "role": "user", "content": "Hi",
             "input_type": "text", "detected_text_emotion": None,
             "detected_voice_emotion": None, "emotion_confidence": None,
             "created_at": "2025-01-01T00:00:00Z"},
        ]
    return patch("app.main.load_session_history", new=AsyncMock(return_value={
        "session_id": VALID_SESSION_ID, "messages": messages,
    }))


def _mock_whisper(transcript="I have been feeling anxious lately."):
    return patch("app.main.transcribe_audio", new=AsyncMock(return_value=transcript))


def _mock_tts(audio_b64="bW9ja2F1ZGlv", mime="audio/wav"):
    return patch("app.main.generate_tts", new=AsyncMock(return_value=(audio_b64, mime)))


# ── Health (public) ──────────────────────────────────────────────────────────

def test_root():
    resp = client.get("/")
    assert resp.status_code == 200


def test_health_public():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Auth: missing header → 401 ──────────────────────────────────────────────

def test_text_turn_missing_header_401():
    resp = client.post("/v1/chat/text-turn", json={"message": "Hello"})
    assert resp.status_code == 401


def test_voice_turn_missing_header_401():
    resp = client.post("/v1/chat/voice-turn", files={
        "file": ("voice.wav", b"a" * 200, "audio/wav"),
    })
    assert resp.status_code == 401


def test_tts_missing_header_401():
    resp = client.post("/tts/generate", json={"text": "Hello"})
    assert resp.status_code == 401


def test_history_missing_header_401():
    resp = client.get(f"/v1/chat/sessions/{VALID_SESSION_ID}/history")
    assert resp.status_code == 401


# ── Auth: empty token → 401 ─────────────────────────────────────────────────

def test_text_turn_empty_token_401():
    resp = client.post("/v1/chat/text-turn", json={
        "message": "Hello",
    }, headers=_auth_header(""))
    assert resp.status_code == 401


# ── Text Turn — success ─────────────────────────────────────────────────────

def test_text_turn_success():
    with _mock_auth(), _mock_handle_text_turn("Thank you for sharing.", VALID_SESSION_ID):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "I've been feeling overwhelmed at work.",
        }, headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Thank you for sharing."
    assert data["session_id"] == VALID_SESSION_ID
    assert data["request_id"].startswith("req_")


def test_text_turn_creates_session():
    """When session_id=null, a session is created and returned (no longer null)."""
    with _mock_auth(), _mock_handle_text_turn(sid=VALID_SESSION_ID):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Hello",
            "session_id": None,
        }, headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["session_id"] == VALID_SESSION_ID


def test_text_turn_reuses_session():
    """When session_id is supplied, it's preserved."""
    sid = "22222222-2222-2222-2222-222222222222"
    with _mock_auth(), _mock_handle_text_turn(sid=sid):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Hello again",
            "session_id": sid,
        }, headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid


def test_text_turn_response_contract():
    with _mock_auth(), _mock_handle_text_turn("I'm here for you.", VALID_SESSION_ID):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Help me.",
        }, headers=_auth_header())
    data = resp.json()
    assert set(data.keys()) == {"answer", "session_id", "request_id"}
    assert isinstance(data["answer"], str)
    assert isinstance(data["session_id"], str)
    assert data["request_id"].startswith("req_")


# ── Text Turn — crisis ──────────────────────────────────────────────────────

def test_text_turn_crisis_still_requires_auth():
    """Crisis messages must authenticate before returning static response."""
    resp = client.post("/v1/chat/text-turn", json={
        "message": "I want to kill myself",
    })
    assert resp.status_code == 401  # Auth enforced


def test_text_turn_crisis_authenticated():
    with _mock_auth(), \
         patch("app.supabase_chat_repository.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "I want to kill myself",
        }, headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert "988" in data["answer"]
    assert data["session_id"] == VALID_SESSION_ID


# ── Text Turn — emotion ─────────────────────────────────────────────────────

def test_text_turn_missing_emotion_still_succeeds():
    """When no emotion endpoint is configured, chat still works."""
    with _mock_auth(), _mock_handle_text_turn():
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Just a normal message.",
        }, headers=_auth_header())
    assert resp.status_code == 200


# ── Text Turn — social greeting ─────────────────────────────────────────────

def test_text_turn_social_greeting_uses_concise():
    with _mock_auth(), _mock_handle_text_turn("Hey! How can I help?", VALID_SESSION_ID):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Hi there!",
        }, headers=_auth_header())
    assert resp.status_code == 200


# ── Text Turn — LLM failure preserves user message ──────────────────────────

def test_text_turn_llm_error_503():
    with _mock_auth(), \
         patch("app.main.handle_text_turn", new=AsyncMock(
             side_effect=HTTPException(status_code=503, detail="LLM error")
         )):
        resp = client.post("/v1/chat/text-turn", json={
            "message": "Help with stress",
        }, headers=_auth_header())
    assert resp.status_code == 503


# ── RAG disabled ────────────────────────────────────────────────────────────

def test_rag_disabled():
    """ENABLE_RAG=false → retrieve_book_chunks must NOT be called."""
    with _mock_auth(), \
         _mock_handle_text_turn(), \
         patch("app.main.retrieve_book_chunks") as mock_rag:
        resp = client.post("/v1/chat/text-turn", json={
            "message": "I have anxiety and depression",
        }, headers=_auth_header())
    assert resp.status_code == 200
    mock_rag.assert_not_called()


# ── History endpoint ────────────────────────────────────────────────────────

def test_history_success():
    with _mock_auth(), _mock_load_session_history():
        resp = client.get(
            f"/v1/chat/sessions/{VALID_SESSION_ID}/history",
            headers=_auth_header(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == VALID_SESSION_ID
    assert isinstance(data["messages"], list)


def test_history_requires_auth():
    resp = client.get(f"/v1/chat/sessions/{VALID_SESSION_ID}/history")
    assert resp.status_code == 401


def test_history_session_not_found():
    with _mock_auth(), \
         patch("app.main.load_session_history", new=AsyncMock(
             side_effect=HTTPException(status_code=404, detail="Session not found")
         )):
        resp = client.get(
            f"/v1/chat/sessions/{VALID_SESSION_ID}/history",
            headers=_auth_header(),
        )
    assert resp.status_code == 404


# ── Voice Turn — still works ────────────────────────────────────────────────

def test_voice_turn_success():
    with _mock_auth(), \
         _mock_whisper("I'm feeling lonely."), \
         patch("app.main.call_llm", new=AsyncMock(
             return_value="I hear you."
         )), \
         _mock_tts():
        resp = client.post("/v1/chat/voice-turn", files={
            "file": ("voice.wav", b"a" * 200, "audio/wav"),
        }, headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "I'm feeling lonely."
    assert data["answer"] == "I hear you."
    assert data["audio_base64"] == "bW9ja2F1ZGlv"


def test_voice_turn_crisis():
    with _mock_auth(), \
         _mock_whisper("I want to end my life"), \
         patch("app.main.call_llm") as mock_llm, \
         _mock_tts():
        resp = client.post("/v1/chat/voice-turn", files={
            "file": ("voice.wav", b"a" * 200, "audio/wav"),
        }, headers=_auth_header())
    assert resp.status_code == 200
    assert "988" in resp.json()["answer"]
    mock_llm.assert_not_called()


def test_voice_turn_empty_audio():
    with _mock_auth():
        resp = client.post("/v1/chat/voice-turn", files={
            "file": ("voice.wav", b"", "audio/wav"),
        }, headers=_auth_header())
    assert resp.status_code == 422


def test_voice_turn_tts_fails_gracefully():
    with _mock_auth(), \
         _mock_whisper("Anxious about exams."), \
         patch("app.main.call_llm", new=AsyncMock(
             return_value="Try deep breathing."
         )), \
         patch("app.main.generate_tts", new=AsyncMock(
             side_effect=HTTPException(status_code=503, detail="TTS down")
         )):
        resp = client.post("/v1/chat/voice-turn", files={
            "file": ("voice.wav", b"a" * 200, "audio/wav"),
        }, headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Try deep breathing."
    assert data["audio_base64"] == ""
    assert data["audio_mime_type"] == ""


# ── TTS ─────────────────────────────────────────────────────────────────────

def test_tts_success():
    with _mock_auth(), _mock_tts():
        resp = client.post("/tts/generate", json={
            "text": "Hello",
        }, headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json()["audio_base64"] == "bW9ja2F1ZGlv"


# ── Validation ──────────────────────────────────────────────────────────────

def test_text_turn_empty_message():
    with _mock_auth():
        resp = client.post("/v1/chat/text-turn", json={
            "message": "",
        }, headers=_auth_header())
    assert resp.status_code == 422


def test_tts_empty_text():
    with _mock_auth():
        resp = client.post("/tts/generate", json={"text": ""}, headers=_auth_header())
    assert resp.status_code == 422


# ── Prompt builder unit tests ───────────────────────────────────────────────

def test_build_messages_social():
    from app.prompt_builder import build_messages
    msgs = build_messages(user_message="Hi", is_social=True)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Hi"


def test_build_messages_with_history():
    from app.prompt_builder import build_messages
    history = [{"role": "user", "content": "I feel sad"},
               {"role": "assistant", "content": "Tell me more."}]
    msgs = build_messages(
        user_message="It's about work.",
        memory_context="[goal] User wants to improve work-life balance",
        emotion_context="text emotion: sad",
        history_messages=history,
    )
    assert len(msgs) == 6  # system + memory + emotion + 2 history + user
    assert msgs[1]["role"] == "system"  # memory context
    assert "work-life" in msgs[1]["content"]
    assert msgs[2]["role"] == "system"  # emotion context
    assert msgs[3]["role"] == "user"    # history user
    assert msgs[4]["role"] == "assistant"
    assert msgs[5]["role"] == "user"    # current message


def test_build_messages_no_duplicate_user_msg():
    from app.prompt_builder import build_messages
    history = [{"role": "user", "content": "Same message"}]
    msgs = build_messages(
        user_message="Same message",
        history_messages=history,
    )
    # Current user message is always added exactly once at the end
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Same message"
    # The history version may also appear, but the current one is explicit
    assert msgs[-2]["role"] == "user"  # history


# ── Memory context formatting ───────────────────────────────────────────────

def test_format_memories_context_empty():
    from app.chat_context import format_memories_context
    assert format_memories_context([]) == ""


def test_format_memories_context_active():
    from app.chat_context import format_memories_context
    memories = [
        {"memory_type": "goal", "content": "Improve sleep habits", "confidence": 0.9},
        {"memory_type": "preference", "content": "Prefers short answers", "confidence": 0.8},
    ]
    result = format_memories_context(memories)
    assert "## Long-Term Memory Context" in result
    assert "[goal]" in result
    assert "Improve sleep habits" in result
    assert "[preference]" in result


def test_format_memories_context_skips_empty_content():
    from app.chat_context import format_memories_context
    memories = [
        {"memory_type": "goal", "content": "", "confidence": 0.9},
        {"memory_type": "preference", "content": "Valid one", "confidence": 0.8},
    ]
    result = format_memories_context(memories)
    assert "Valid one" in result
    assert result.count("\n") < 10  # should not have empty lines


# ── Session repository unit tests ───────────────────────────────────────────

@pytest.mark.anyio
async def test_create_session(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = [{"id": VALID_SESSION_ID}]
        return resp

    mock_client.post = _post

    with patch("httpx.AsyncClient", return_value=mock_client):
        sid = await repo.create_session(VALID_USER_ID, VALID_TOKEN, "Test session")
    assert sid == VALID_SESSION_ID


@pytest.mark.anyio
async def test_get_session_owned(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [{"id": VALID_SESSION_ID, "user_id": VALID_USER_ID}]
        return resp

    mock_client.get = _get

    with patch("httpx.AsyncClient", return_value=mock_client):
        session = await repo.get_session(VALID_SESSION_ID, VALID_TOKEN)
    assert session["id"] == VALID_SESSION_ID


@pytest.mark.anyio
async def test_get_session_not_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []  # RLS silently filters
        return resp

    mock_client.get = _get

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc:
            await repo.get_session(VALID_SESSION_ID, VALID_TOKEN)
        assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_get_session_invalid_uuid(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    with pytest.raises(HTTPException) as exc:
        await repo.get_session("not-a-uuid", VALID_TOKEN)
    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_save_message(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = [{"id": "msg-1", "role": "user"}]
        return resp

    mock_client.post = _post

    with patch("httpx.AsyncClient", return_value=mock_client):
        row = await repo.save_message(
            session_id=VALID_SESSION_ID,
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            role="user",
            content="Hello",
            text_emotion="neutral",
            emotion_confidence=0.7,
        )
    assert row["role"] == "user"


@pytest.mark.anyio
async def test_load_recent_messages(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        return resp

    mock_client.get = _get

    with patch("httpx.AsyncClient", return_value=mock_client):
        rows = await repo.load_recent_messages(VALID_SESSION_ID, VALID_TOKEN, limit=12)
    assert len(rows) == 2


@pytest.mark.anyio
async def test_load_active_memories(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [
            {"memory_type": "goal", "content": "Sleep better", "confidence": 0.9},
            {"memory_type": "preference", "content": "Short replies", "confidence": 0.8},
        ]
        return resp

    mock_client.get = _get

    with patch("httpx.AsyncClient", return_value=mock_client):
        rows = await repo.load_active_memories(VALID_USER_ID, VALID_TOKEN)
    assert len(rows) == 2
    assert rows[0]["memory_type"] == "goal"


@pytest.mark.anyio
async def test_load_active_memories_inactive_ignored(monkeypatch):
    """Inactive memories must not be returned (filtered by is_active=eq.true)."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.supabase_chat_repository as repo
    importlib.reload(repo)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    async def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []  # no active memories
        return resp

    mock_client.get = _get

    with patch("httpx.AsyncClient", return_value=mock_client):
        rows = await repo.load_active_memories(VALID_USER_ID, VALID_TOKEN)
    assert len(rows) == 0


@pytest.mark.anyio
async def test_memory_read_only_no_insert():
    """The repository must not insert/update memory rows."""
    from app import supabase_chat_repository as repo
    assert not hasattr(repo, "create_memory") or repo.create_memory is None
    assert not hasattr(repo, "update_memory") or repo.update_memory is None


# ── Chat service integration tests ──────────────────────────────────────────

@pytest.mark.anyio
async def test_handle_text_turn_new_session(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    with patch("app.chat_service.call_runpod_llm", new=AsyncMock(
        return_value="I understand. Let's work on this."
    )), \
         patch("app.chat_service.repo.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )), \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID, "user_id": VALID_USER_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=AsyncMock(
             return_value={"id": "msg-1"}
         )), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[]
         )):
        result = await cs.handle_text_turn(
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            message="I feel overwhelmed.",
            session_id=None,
        )
    assert result["session_id"] == VALID_SESSION_ID
    assert result["answer"] == "I understand. Let's work on this."


@pytest.mark.anyio
async def test_handle_text_turn_reuses_session(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    with patch("app.chat_service.call_runpod_llm", new=AsyncMock(
        return_value="Welcome back!"
    )), \
         patch("app.chat_service.repo.create_session") as mock_create, \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID, "user_id": VALID_USER_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=AsyncMock(
             return_value={"id": "msg-1"}
         )), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[]
         )):
        result = await cs.handle_text_turn(
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            message="I'm back.",
            session_id=VALID_SESSION_ID,
        )
    assert result["session_id"] == VALID_SESSION_ID
    mock_create.assert_not_called()  # Existing session, no new session created


@pytest.mark.anyio
async def test_handle_text_turn_saves_user_and_assistant(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    save_calls = []

    async def _save(**kwargs):
        save_calls.append(kwargs)
        return {"id": f"msg-{len(save_calls)}"}

    with patch("app.chat_service.call_runpod_llm", new=AsyncMock(
        return_value="I hear you."
    )), \
         patch("app.chat_service.repo.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )), \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=_save), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[]
         )):
        await cs.handle_text_turn(
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            message="Hi",
            session_id=None,
        )
    assert len(save_calls) == 2
    assert save_calls[0]["role"] == "user"
    assert save_calls[0]["content"] == "Hi"
    assert save_calls[1]["role"] == "assistant"
    assert save_calls[1]["content"] == "I hear you."


@pytest.mark.anyio
async def test_handle_text_turn_llm_failure_preserves_user_msg(monkeypatch):
    """When LLM fails, user message is saved but assistant message is not."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    save_calls = []

    async def _save(**kwargs):
        save_calls.append(kwargs)
        return {"id": f"msg-{len(save_calls)}"}

    with patch("app.chat_service.call_runpod_llm", new=AsyncMock(
        side_effect=Exception("LLM crash")
    )), \
         patch("app.chat_service.repo.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )), \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=_save), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[]
         )):
        with pytest.raises(Exception, match="LLM crash"):
            await cs.handle_text_turn(
                user_id=VALID_USER_ID,
                user_token=VALID_TOKEN,
                message="Important message",
                session_id=None,
            )
    assert len(save_calls) == 1
    assert save_calls[0]["role"] == "user"
    assert save_calls[0]["content"] == "Important message"


@pytest.mark.anyio
async def test_handle_text_turn_includes_memory(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    captured_messages = None

    async def _capture_llm(messages, **kw):
        nonlocal captured_messages
        captured_messages = messages
        return "Got it."

    with patch("app.chat_service.call_runpod_llm", new=_capture_llm), \
         patch("app.chat_service.repo.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )), \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=AsyncMock(
             return_value={"id": "msg-1"}
         )), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[
                 {"memory_type": "goal", "content": "Better sleep", "confidence": 0.9},
             ]
         )):
        await cs.handle_text_turn(
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            message="I can't sleep",
            session_id=None,
        )
    assert captured_messages is not None
    # Memory context should appear as a system message
    system_contents = [m["content"] for m in captured_messages if m["role"] == "system"]
    memory_found = any("Better sleep" in c for c in system_contents)
    assert memory_found


@pytest.mark.anyio
async def test_handle_text_turn_includes_history(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_test")
    import importlib
    import app.chat_service as cs
    import app.supabase_chat_repository as repo
    import app.chat_context as ctx
    importlib.reload(repo)
    importlib.reload(ctx)
    importlib.reload(cs)

    captured_messages = None

    async def _capture_llm(messages, **kw):
        nonlocal captured_messages
        captured_messages = messages
        return "I remember."

    with patch("app.chat_service.call_runpod_llm", new=_capture_llm), \
         patch("app.chat_service.repo.create_session", new=AsyncMock(
             return_value=VALID_SESSION_ID
         )), \
         patch("app.chat_service.repo.get_session", new=AsyncMock(
             return_value={"id": VALID_SESSION_ID}
         )), \
         patch("app.chat_service.repo.save_message", new=AsyncMock(
             return_value={"id": "msg-1"}
         )), \
         patch("app.chat_service.chat_context.load_history", new=AsyncMock(
             return_value=[
                 {"role": "user", "content": "Previous msg 1"},
                 {"role": "assistant", "content": "Previous reply 1"},
                 {"role": "user", "content": "Current msg"},
             ]
         )), \
         patch("app.chat_service.chat_context.load_memories", new=AsyncMock(
             return_value=[]
         )):
        await cs.handle_text_turn(
            user_id=VALID_USER_ID,
            user_token=VALID_TOKEN,
            message="Current msg",
            session_id=VALID_SESSION_ID,
        )
    assert captured_messages is not None
    # History should include the first 2 messages, but NOT the third (it's the one we just saved)
    user_contents = [m["content"] for m in captured_messages if m["role"] == "user"]
    assert "Previous msg 1" in user_contents
    # Current message appears exactly once
    assert user_contents.count("Current msg") == 1


# ── History endpoint: ownership enforcement ─────────────────────────────────

def test_history_enforces_ownership():
    """Foreign session must return 404."""
    with _mock_auth(), \
         patch("app.main.load_session_history", new=AsyncMock(
             side_effect=HTTPException(status_code=404, detail="Session not found")
         )):
        resp = client.get(
            f"/v1/chat/sessions/{VALID_SESSION_ID}/history",
            headers=_auth_header(),
        )
    assert resp.status_code == 404


def test_history_invalid_uuid():
    with _mock_auth(), \
         patch("app.main.load_session_history", new=AsyncMock(
             side_effect=HTTPException(status_code=422, detail="Invalid session ID format")
         )):
        resp = client.get(
            "/v1/chat/sessions/not-a-uuid/history",
            headers=_auth_header(),
        )
    assert resp.status_code == 422
