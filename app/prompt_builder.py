"""
Shared prompt builder — constructs the final message list sent to the LLM.

Designed to be reused by both text-turn and voice-turn (future).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Maximum total messages including system prompts and history.
# RunPod serverless worker supports up to 20.
MAX_TOTAL_MESSAGES = 20


# ── System prompts ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI mental health support assistant acting as a warm, empathetic therapist and life coach.

Core behavior:
- Use Cognitive Behavioral Therapy (CBT) techniques when relevant.
- Validate emotions before giving guidance.
- Be calm, friendly, non-judgmental, and supportive.
- Speak in a natural, human tone suitable for Gen-Z and Gen-Alpha.
- Use motivational-interviewing style: reflect, explore, gently guide.
- Offer practical, realistic next steps.
- Match your response length to the user's message.
- Ask at most one useful follow-up question unless more are necessary.
- Respect user autonomy.

Content rules (VERY IMPORTANT):
- Never invent symptoms, emotions, diagnoses, history, intentions, or life circumstances.
- Never assume anxiety, depression, loneliness, trauma, or crisis without user evidence.
- Respond ONLY to what the user actually said.
- Do not turn ordinary conversation into therapy.
- Avoid lists unless the user explicitly requests one.
- Default to 1–4 short sentences.
- Simple greetings stay under 30 words.
- Longer answers only when the user explicitly requests more detail.

Safety rules:
- Do NOT diagnose.
- Do NOT give medical or clinical advice.
- Do NOT prescribe medication.
- Do NOT pretend to be a licensed therapist.
- If the user expresses suicidal thoughts, self-harm, or crisis, respond with empathy and encourage professional/emergency support.
- Never act as a replacement for professional care.

Your goal:
Help the user feel heard, supported, and gently guided — like a trusted therapist and friend.
"""

CONCISE_SOCIAL_PROMPT = """You are a warm, friendly mental-health AI assistant. The user has just sent a simple social message (greeting, introduction, or thanks). Respond naturally in 1–2 short sentences. Do NOT interpret this as a therapy session. Do NOT assume any emotional state. Just be welcoming and conversational."""


# ── Emotion context formatter ───────────────────────────────────────────────

def format_emotion_context(
    text_emotion: Optional[Dict[str, Any]],
    voice_emotion: Optional[Dict[str, Any]],
) -> str:
    """Build a short emotion-hint string for the system context."""
    parts: List[str] = []
    if text_emotion:
        top = text_emotion.get("top_emotion") or text_emotion.get("emotion", "")
        if top:
            parts.append(f"text emotion: {top}")
    if voice_emotion:
        top = voice_emotion.get("top_emotion") or voice_emotion.get("emotion", "")
        if top:
            parts.append(f"voice emotion: {top}")
    if not parts:
        return ""
    return (
        "Emotion signals detected: " + "; ".join(parts) + ". "
        "Use these only as soft tone hints — do not diagnose or overstate."
    )

def build_messages(
    *,
    user_message: str,
    is_social: bool = False,
    memory_context: str = "",
    emotion_context: str = "",
    history_messages: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Build the ordered message list for the RunPod LLM.

    Order:
      1. Main system prompt (or concise social prompt)
      2. Memory context (if present)
      3. Emotion context (if present)
      4. Recent user/assistant history messages
      5. Current user message (exactly once)

    The history messages should NOT include the current user message —
    that is added separately here to avoid duplication.
    """
    messages: List[Dict[str, str]] = []

    # 1. System prompt
    if is_social:
        messages.append({"role": "system", "content": CONCISE_SOCIAL_PROMPT})
    else:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

    # 2. Memory context
    if memory_context:
        messages.append({"role": "system", "content": memory_context})

    # 3. Emotion context
    if emotion_context:
        messages.append({"role": "system", "content": emotion_context})

    # 4. History messages (already filtered to user/assistant roles)
    if history_messages:
        remaining_slots = MAX_TOTAL_MESSAGES - len(messages) - 1  # -1 for user msg
        if remaining_slots > 0:
            messages.extend(history_messages[-remaining_slots:])

    # 5. Current user message
    messages.append({"role": "user", "content": user_message})

    return messages
