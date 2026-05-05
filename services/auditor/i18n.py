"""
Internationalisation constants for the Clinical Auditor.

Crisis keywords, guidance messages, and hotline data for English and Arabic.
All auditor-facing strings must be imported from this module only.
"""

from __future__ import annotations

from typing import Dict, List


# ---------------------------------------------------------------------------
# Crisis keyword lists (case-insensitive matching done by the auditor)
# ---------------------------------------------------------------------------

CRISIS_KEYWORDS_EN: List[str] = [
    "suicide",
    "kill myself",
    "end my life",
    "harm myself",
    "self-harm",
    "self harm",
    "suicidal",
    "overdose",
    "immediate danger",
    "want to die",
    "can't go on",
    "cant go on",
    "no reason to live",
    "hurt myself",
    "cut myself",
    "jump off",
    "hang myself",
    "poison myself",
    "take pills",
    "shoot myself",
    "end it all",
    "don't want to live",
    "dont want to live",
    "ending it all",
    "better off dead",
    "kill me",
]

CRISIS_KEYWORDS_AR: List[str] = [
    "انتحار",
    "انتحر",
    "اقتل نفسي",
    "أقتل نفسي",
    "انهي حياتي",
    "أنهي حياتي",
    "ايذاء نفسي",
    "إيذاء نفسي",
    "اذي نفسي",
    "أذي نفسي",
    "انتحاري",
    "انتحارية",
    "جرعة زائدة",
    "خطر فوري",
    "اريد الموت",
    "أريد الموت",
    "أريد أن أموت",
    "ما ارد العيش",
    "ما أريد العيش",
    "ما عندي سبب للعيش",
    "م عندي سبب للعيش",
    "اضرب نفسي",
    "أضرب نفسي",
    "اجرح نفسي",
    "أجرح نفسي",
    "اقطع نفسي",
    "أقطع نفسي",
    "ارمي حالي",
    "أرمي حالي",
    "اشنق حالي",
    "أشنق حالي",
    "ما في سبب عيش",
]


# ---------------------------------------------------------------------------
# Robotic tone keywords — detect AI-disclaimer language
# ---------------------------------------------------------------------------

ROBOTIC_TONE_KEYWORDS: List[str] = [
    "as an ai",
    "language model",
    "i cannot",
    "i'm just",
    "for informational purposes only",
    "i don't have",
    "i am not a doctor",
    "i can't provide medical advice",
    "i can't diagnose",
    "cannot diagnose",
]


# ---------------------------------------------------------------------------
# Guidance messages by locale and severity level
# ---------------------------------------------------------------------------

GUIDANCE_MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "red": (
            "I'm really sorry you're going through this. If you feel in immediate danger, "
            "or you're thinking about harming yourself, please contact your local emergency number now. "
            "If you can, reach out right away to a trusted person or support line, and seek urgent "
            "help from a qualified mental health professional."
        ),
        "yellow": (
            "Here are personalized next steps based on your responses and screen-time pattern. "
            "Please treat these as general guidance and consider discussing them with a qualified clinician."
        ),
    },
    "ar": {
        "red": (
            "أنا آسف لأنك تمرّ بهذا. إذا كنت في خطر فوري أو تفكر في إيذاء نفسك، "
            "فالرجاء الاتصال برقم الطوارئ المحلي فورًا. إن استطعت، تواصل حالًا مع شخص موثوق أو خط دعم، "
            "واطلب مساعدة عاجلة من مختص/ة بالصحة النفسية."
        ),
        "yellow": (
            "هذه خطوات تالية مُخصصة بناءً على إجاباتك ونمط وقت الشاشة. "
            "يرجى اعتبارها إرشادات عامة، وفكّر في مناقشتها مع مختص/ة مؤهل/ة."
        ),
    },
}


# ---------------------------------------------------------------------------
# Hotline / emergency resource data
# ---------------------------------------------------------------------------

HOTLINES: Dict[str, List[Dict[str, str]]] = {
    "en": [
        {
            "name": "Emergency Services",
            "number": "911",
            "description": "Call for immediate life-threatening emergencies",
        },
        {
            "name": "988 Suicide & Crisis Lifeline",
            "number": "988",
            "description": "Free, confidential, 24/7 support for people in distress",
        },
        {
            "name": "Crisis Text Line",
            "number": "Text HOME to 741741",
            "description": "Free crisis counseling via text message",
        },
    ],
    "ar": [
        {
            "name": "الطوارئ",
            "number": "911",
            "description": "اتصل في حالات الطوارئ التي تهدد الحياة فورًا",
        },
        {
            "name": "خط المساعدة للأزمات",
            "number": "988",
            "description": "دعم مجاني وسري على مدار الساعة للأشخاص في ضائقة",
        },
        {
            "name": "خط الأزمات عبر الرسائل",
            "number": "HOME إلى 741741",
            "description": "استشارات أزمات مجانية عبر الرسائل النصية",
        },
    ],
}


def resolve_locale(locale: str) -> str:
    """Normalise a locale string to 'en' or 'ar'."""
    if str(locale).lower().startswith("ar"):
        return "ar"
    return "en"
