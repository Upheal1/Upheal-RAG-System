"""
UpHeal AI Backend — FastAPI application

Endpoints:
  POST /v1/chat/text-turn   — text chat
  POST /v1/chat/voice-turn  — voice chat (multipart)
  POST /tts/generate         — TTS generation
  GET  /v1/chat/sessions/{session_id}/history  — message history
  GET  /health               — health check
  GET  /v1/health            — health check
"""

from __future__ import annotations

import base64
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.runpod_llm_client import (
    RunPodLLMError,
    RunPodConfigError,
    RunPodAuthError,
    RunPodRateLimitError,
    RunPodJobFailedError,
    RunPodTimeoutError,
    RunPodOutputError,
    call_runpod_llm,
)
from app.prompt_builder import SYSTEM_PROMPT, CONCISE_SOCIAL_PROMPT, format_emotion_context
from app.chat_service import handle_text_turn, load_session_history

logger = logging.getLogger("upheal")
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Config (via environment variables)
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# SUPABASE_PUBLISHABLE_KEY is the preferred name; SUPABASE_ANON_KEY is a
# backward-compatible fallback (both refer to the same publishable/anonymous key).
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

# RunPod serverless LLM (queue-based — replaces old persistent-pod proxy)
# RUNPOD_API_KEY and RUNPOD_LLM_ENDPOINT_ID are required by the client.

RUNPOD_WHISPER_URL = os.getenv("RUNPOD_WHISPER_URL") or os.getenv("RUNPOD_WHISPER_BASE_URL", "")
RUNPOD_TTS_URL = os.getenv("RUNPOD_TTS_URL") or os.getenv("RUNPOD_TTS_BASE_URL", "")

# Optional RunPod emotion endpoints (if unavailable, emotion analysis is skipped)
RUNPOD_VOICE_EMOTION_URL = os.getenv("RUNPOD_VOICE_EMOTION_URL", "")
RUNPOD_TEXT_EMOTION_URL = os.getenv("RUNPOD_TEXT_EMOTION_URL", "")

# RAG (knowledge-base retrieval) — disabled by default
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").strip().lower() in ("1", "true", "yes")

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# GROQ is kept only for the embeddings call inside retrieve_book_chunks()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

DEFAULT_AUDIENCE = "adult"
DEFAULT_LIMIT = 3
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 220
VOICE_DEFAULT_MAX_TOKENS = 180


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Upheal AI Backend", version="0.1.0")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class TextTurnRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=0, le=10)
    audience: str = Field(default=DEFAULT_AUDIENCE, max_length=50)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=1.5)
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=32, le=600)


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Simple social message detection
# ---------------------------------------------------------------------------

_SIMPLE_GREETINGS: List[str] = [
    # English
    r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bheya?\b",
    r"\bgood\s+morning\b", r"\bgood\s+afternoon\b", r"\bgood\s+evening\b",
    r"\bgood\s+night\b",
    r"\bthanks?\b", r"\bthank\s+you\b", r"\bthx\b",
    r"\bhow\s+are\s+you\b", r"\bhow('?s| is)\s+it\s+going\b",
    r"\bmy\s+name\s+is\b", r"\bI\s+am\b", r"\bi('| a)?m\b",
    r"\bnice\s+to\s+meet\s+you\b", r"\bpleased\s+to\s+meet\b",
    r"\byou('?re| are)\s+welcome\b", r"\bno\s+problem\b",
    r"\bok(ay)?\b", r"\byes\b", r"\byeah\b", r"\bnope?\b",
    # Arabic
    r"\bمرحبا\b", r"\bاهلا\b", r"\bأهلا\b", r"\bأهلاً\b", r"\bاهلاً\b",
    r"\bالسلام\s+عليكم\b", r"\bوعليكم\s+السلام\b",
    r"\bشكرا\b", r"\bشكراً\b",
    r"\bاسمي\b", r"\bانا\b", r"\bأنا\b",
    r"\bكيف\s+الحال\b", r"\bكيفك\b",
    r"\bصباح\s+الخير\b", r"\bمساء\s+الخير\b",
]

_compiled_greetings: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _SIMPLE_GREETINGS
]

_SIMPLE_TOPICS: List[str] = [
    r"\bemotional\s+support\b", r"\btherapy\b", r"\btherapeutic\b",
    r"\bmental\s+health\b", r"\bdepress(ed|ion)\b", r"\banxi(ous|ety)\b",
    r"\bpanic\b", r"\btrauma\b", r"\bCBT\b", r"\bcogni(tive|tional)\b",
    r"\bcoping\b", r"\bgrounding\b", r"\bmindful(ness)?\b",
    r"\bself[\s-]harm\b", r"\bsuicid(al|e)\b",
    r"\bstress(ed|ful)?\b", r"\boverwhelm(ed|ing)?\b",
    r"\blonely\b", r"\bloneliness\b", r"\bgrief\b",
    r"\bmeditation\b", r"\bbreathing\b", r"\brelaxation\b",
    r"\binsomnia\b", r"\bsleep\s+(problem|issue|disorder)\b",
    r"\bPTSD\b", r"\bOCD\b", r"\bADHD\b",
]

_compiled_topics: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _SIMPLE_TOPICS
]


def is_simple_social_message(message: str) -> bool:
    """Return True when `message` is a greeting, introduction, thanks,
    or casual social opening — not a therapeutic or topic-seeking turn."""
    stripped = message.strip().rstrip("!.?")
    if len(stripped) <= 3:
        return True

    for p in _compiled_greetings:
        if p.search(stripped):
            for tp in _compiled_topics:
                if tp.search(stripped):
                    return False
            return True

    return False


def should_retrieve_chunks(message: str) -> bool:
    """Return True when RAG retrieval is warranted — explicit mental-health,
    CBT, therapy, or factual-guidance questions."""
    stripped = message.strip()
    for tp in _compiled_topics:
        if tp.search(stripped):
            return True
    return False


# ---------------------------------------------------------------------------
# Crisis detection
# ---------------------------------------------------------------------------

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "want to die",
    "self-harm", "hurt myself", "cut myself",
    "no reason to live", "better off dead", "don't want to be here",
    "الانتحار", "أريد الموت", "أذى نفسي",
]

CRISIS_RESPONSE = (
    "I hear you, and I'm really glad you reached out. "
    "You're not alone. Please contact emergency services or a trusted person "
    "right now. If you're in the US, call or text 988 for the Suicide & Crisis "
    "Lifeline. For other countries, please dial your local emergency number. "
    "I'm here to support you, but I can't replace professional crisis care."
)


def is_crisis_message(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in CRISIS_KEYWORDS)


# ---------------------------------------------------------------------------
# Supabase authentication
# ---------------------------------------------------------------------------

async def _verify_token(token: str) -> Dict[str, Any]:
    """Call Supabase /auth/v1/user.  Returns the parsed JSON body.

    Raises HTTPException(503) when Supabase is unreachable.
    Raises HTTPException(401) when the token is invalid/expired.
    """
    if not SUPABASE_URL:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    if not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(status_code=503, detail="Supabase publishable key not configured")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                },
                timeout=10,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Supabase auth timed out")
    except httpx.RequestError as exc:
        logger.warning("Supabase auth request failed: %s", exc)
        raise HTTPException(status_code=503, detail="Supabase auth unavailable")

    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    if resp.status_code >= 500:
        raise HTTPException(status_code=503, detail="Supabase auth error")
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="Supabase auth unexpected response")

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=503, detail="Supabase returned invalid JSON")


async def require_auth(authorization: Optional[str]) -> tuple[str, str]:
    """Validate the Bearer token and return (user_id, access_token).

    Always raises HTTPException(401) when the Authorization header is missing,
    empty, or the token is invalid/expired.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token")
    data = await _verify_token(token)
    user_id: Optional[str] = data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token payload missing user id")
    return user_id, token


async def verify_supabase_token(authorization: Optional[str]) -> Optional[str]:
    """Non-mandatory variant — returns None instead of raising on failure."""
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        data = await _verify_token(token)
        return data.get("id")
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# RAG / Qdrant
# ---------------------------------------------------------------------------

async def retrieve_book_chunks(query: str, limit: int = 3) -> List[str]:
    """Retrieve relevant book chunks from Qdrant."""
    if not QDRANT_URL:
        return []
    try:
        async with httpx.AsyncClient() as client:
            embed_resp = await client.post(
                f"{GROQ_CHAT_URL.replace('/chat/completions', '/embeddings')}",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-ada-002",
                    "input": query,
                },
                timeout=15,
            )
            if embed_resp.status_code != 200:
                logger.warning("Embedding failed: %s", embed_resp.status_code)
                return []
            embedding = embed_resp.json()["data"][0]["embedding"]

            search_resp = await client.post(
                f"{QDRANT_URL}/collections/upheal_kb/points/search",
                headers={
                    "api-key": QDRANT_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "vector": embedding,
                    "limit": limit,
                    "with_payload": True,
                },
                timeout=10,
            )
            if search_resp.status_code != 200:
                logger.warning("Qdrant search failed: %s", search_resp.status_code)
                return []
            results = search_resp.json().get("result", [])
            return [
                p.get("payload", {}).get("text", "")
                for p in results
            ]
    except Exception:
        logger.exception("RAG retrieval failed")
        return []


# ---------------------------------------------------------------------------
# LLM — RunPod queue-based serverless
# ---------------------------------------------------------------------------

async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Call RunPod serverless LLM (queue-based)."""
    try:
        return await call_runpod_llm(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RunPodConfigError as exc:
        raise HTTPException(status_code=503, detail=f"LLM config error: {exc}")
    except RunPodAuthError as exc:
        raise HTTPException(status_code=503, detail=f"LLM auth error: {exc}")
    except RunPodRateLimitError as exc:
        raise HTTPException(status_code=503, detail=f"LLM rate limited: {exc}")
    except RunPodTimeoutError as exc:
        raise HTTPException(status_code=503, detail=f"LLM timeout: {exc}")
    except RunPodJobFailedError as exc:
        raise HTTPException(status_code=503, detail=f"LLM job failed: {exc}")
    except RunPodOutputError as exc:
        raise HTTPException(status_code=503, detail=f"LLM output error: {exc}")
    except RunPodLLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected LLM error")
        raise HTTPException(status_code=503, detail=f"LLM error: {exc}")


# ---------------------------------------------------------------------------
# Emotion analysis (text / voice)
# ---------------------------------------------------------------------------

async def analyze_text_emotion(text: str) -> Optional[Dict[str, Any]]:
    """Call the RunPod text-emotion endpoint. Returns None on any failure."""
    if not RUNPOD_TEXT_EMOTION_URL:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RUNPOD_TEXT_EMOTION_URL,
                json={"text": text},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning("Text emotion HTTP %s", resp.status_code)
                return None
            return resp.json()
    except Exception:
        logger.warning("Text emotion unavailable", exc_info=True)
        return None


async def analyze_voice_emotion(file_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Call the RunPod voice-emotion endpoint. Returns None on any failure."""
    if not RUNPOD_VOICE_EMOTION_URL:
        return None
    try:
        audio_b64 = base64.b64encode(file_bytes).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RUNPOD_VOICE_EMOTION_URL,
                json={"audio": audio_b64},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("Voice emotion HTTP %s", resp.status_code)
                return None
            return resp.json()
    except Exception:
        logger.warning("Voice emotion unavailable", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Whisper (STT) via RunPod
# ---------------------------------------------------------------------------

async def transcribe_audio(file_bytes: bytes) -> str:
    if not RUNPOD_WHISPER_URL:
        raise HTTPException(status_code=503, detail="Whisper service unavailable")

    audio_b64 = base64.b64encode(file_bytes).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            RUNPOD_WHISPER_URL,
            json={"audio": audio_b64},
            timeout=60,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Transcription failed")
        data = resp.json()
        return data.get("text", data.get("transcript", ""))


# ---------------------------------------------------------------------------
# TTS via RunPod / Chatterbox
# ---------------------------------------------------------------------------

async def generate_tts(text: str) -> tuple[str, str]:
    """Return (base64_audio, mime_type)."""
    if not RUNPOD_TTS_URL:
        raise HTTPException(status_code=503, detail="TTS service unavailable")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            RUNPOD_TTS_URL,
            json={"text": text, "voice": "default"},
            timeout=60,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=503, detail="TTS generation failed")

        data = resp.json()
        audio_b64 = data.get("audio_base64", data.get("audio", ""))
        mime = data.get("mime_type", data.get("audio_mime_type", "audio/wav"))
        return audio_b64, mime


# ===================================================================
# Routes
# ===================================================================

@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
@app.get("/v1/health")
async def health():
    kb_healthy = bool(QDRANT_URL)
    return {"status": "ok", "knowledge_base_healthy": kb_healthy}


# ── Text Turn ──────────────────────────────────────────────────────────────

@app.post("/v1/chat/text-turn")
async def text_turn(
    body: TextTurnRequest,
    authorization: Optional[str] = Header(None),
):
    user_id, user_token = await require_auth(authorization)
    message = body.message.strip()

    logger.info(
        "text-turn  user=%s  session=%s  len=%d  simple=%s",
        user_id, body.session_id, len(message), is_simple_social_message(message),
    )

    # Crisis gate (handled before DB/LLM)
    if is_crisis_message(message):
        # For crisis, create a session if needed so session_id is never null
        if not body.session_id:
            from app import supabase_chat_repository as repo
            title = message.strip()[:80]
            sid = await repo.create_session(user_id, user_token, title)
        else:
            sid = body.session_id
        return {
            "answer": CRISIS_RESPONSE,
            "session_id": sid,
            "request_id": f"req_{int(time.time()*1000)}",
        }

    # Text emotion analysis
    text_emotion: Optional[Dict[str, Any]] = None
    if not is_simple_social_message(message):
        text_emotion = await analyze_text_emotion(message)

    # Delegate to chat service (session, history, memory, LLM, persistence)
    try:
        result = await handle_text_turn(
            user_id=user_id,
            user_token=user_token,
            message=message,
            session_id=body.session_id,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            text_emotion=text_emotion,
            is_social=is_simple_social_message(message),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in text-turn")
        raise HTTPException(status_code=503, detail="Chat service error")

    return result


# ── Voice Turn ─────────────────────────────────────────────────────────────

@app.post("/v1/chat/voice-turn")
async def voice_turn(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    limit: int = Form(DEFAULT_LIMIT),
    audience: str = Form(DEFAULT_AUDIENCE),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    max_tokens: int = Form(VOICE_DEFAULT_MAX_TOKENS),
    authorization: Optional[str] = Header(None),
):
    user_id, user_token = await require_auth(authorization)
    file_bytes = await file.read()
    logger.info(
        "voice-turn  user=%s  session=%s  size=%d",
        user_id, session_id, len(file_bytes),
    )

    if len(file_bytes) < 100:
        raise HTTPException(status_code=422, detail="No clear audio detected")

    # 1. STT (Whisper)
    transcript = await transcribe_audio(file_bytes)
    logger.info("transcript: %s", transcript[:100])

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=422, detail="No clear audio detected")

    transcript = transcript.strip()

    # 2. Crisis check
    if is_crisis_message(transcript):
        answer = CRISIS_RESPONSE
    else:
        # 3. Voice emotion analysis
        voice_emotion: Optional[Dict[str, Any]] = None
        text_emotion: Optional[Dict[str, Any]] = None
        if not is_simple_social_message(transcript):
            voice_emotion = await analyze_voice_emotion(file_bytes)
            text_emotion = await analyze_text_emotion(transcript)

        # 4. RAG routing — gated by ENABLE_RAG
        rag_chunks: List[str] = []
        if ENABLE_RAG and should_retrieve_chunks(transcript):
            rag_chunks = await retrieve_book_chunks(transcript, limit=limit)

        # 5. Build messages using prompt_builder
        from app.prompt_builder import build_messages

        emotion_hint = format_emotion_context(text_emotion, voice_emotion)

        msgs = build_messages(
            user_message=transcript,
            is_social=is_simple_social_message(transcript),
            memory_context="",
            emotion_context=emotion_hint,
            history_messages=None,
        )
        # Inject RAG chunks as additional system context if present
        if rag_chunks:
            rag_context = (
                "The following passages are from mental-health reference books. "
                "Use them ONLY if directly relevant to the user's message. "
                "Do NOT treat them as facts about the user.\n\n"
                + "\n\n".join(rag_chunks)
            )
            # Insert after the main system prompt
            msgs.insert(2, {"role": "system", "content": rag_context})

        answer = await call_llm(msgs, temperature, max_tokens)

    # 6. TTS (Chatterbox)
    try:
        audio_b64, audio_mime = await generate_tts(answer)
    except HTTPException:
        audio_b64 = ""
        audio_mime = ""

    return {
        "transcript": transcript,
        "answer": answer,
        "session_id": session_id,
        "request_id": f"req_{int(time.time()*1000)}",
        "audio_base64": audio_b64,
        "audio_mime_type": audio_mime,
    }


# ── TTS (standalone) ────────────────────────────────────────────────────────

@app.post("/tts/generate")
async def tts_generate(
    body: TTSGenerateRequest,
    authorization: Optional[str] = Header(None),
):
    user_id, _ = await require_auth(authorization)
    logger.info("tts-generate  user=%s  text_len=%d", user_id, len(body.text))
    try:
        audio_b64, audio_mime = await generate_tts(body.text)
    except HTTPException as e:
        raise e
    return {"audio_base64": audio_b64, "audio_mime_type": audio_mime}


# ── Session History ─────────────────────────────────────────────────────────

@app.get("/v1/chat/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    authorization: Optional[str] = Header(None),
):
    _, user_token = await require_auth(authorization)
    return await load_session_history(session_id, user_token)
