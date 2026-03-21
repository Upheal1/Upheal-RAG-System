from __future__ import annotations

from typing import List

from services.shared.schemas import ClinicalTask, FinalRoadmap


CRISIS_KEYWORDS: List[str] = [
    "suicide",
    "kill myself",
    "end my life",
    "harm myself",
    "self-harm",
    "suicidal",
    "overdose",
    "immediate danger",
]

ROBOTIC_TONE_KEYWORDS: List[str] = [
    "as an ai",
    "language model",
    "i cannot",
    "i'm just",
    "for informational purposes only",
    "i don't have",
]


def audit_roadmap(roadmap: FinalRoadmap) -> FinalRoadmap:
    """
    Audit the roadmap text for:
    - crisis keywords
    - robotic tone

    Safety rules:
    - If safe: set safety_status = "GREEN"
    - If crisis detected: overwrite with emergency resources and set to "RED"
    """
    text = (roadmap.overview_paragraph or "").lower()
    crisis_detected = any(k in text for k in CRISIS_KEYWORDS)
    robotic_detected = any(k in text for k in ROBOTIC_TONE_KEYWORDS)

    if crisis_detected:
        emergency = (
            "I'm really sorry you're going through this. If you feel in immediate danger, "
            "or you're thinking about harming yourself, please contact your local emergency number now. "
            "If you can, reach out right away to a trusted person or support line, and seek urgent "
            "help from a qualified mental health professional."
        )

        roadmap.overview_paragraph = emergency
        roadmap.safety_status = "RED"
        roadmap.next_checkup_days = 1

        # Replace suggestions with a single safety-oriented task.
        roadmap.suggested_tasks = [
            ClinicalTask(
                task_id="emergency_resources",
                content=emergency,
                symptom_tags=["suicidal"],
                difficulty=5,
                xp_reward=0,
                source_reference="auditor",
                metadata={},
            )
        ]
        return roadmap

    if robotic_detected:
        roadmap.safety_status = "YELLOW"
        roadmap.next_checkup_days = 7
        roadmap.overview_paragraph = (
            "Here are personalized next steps based on your responses and screen-time pattern. "
            "Please treat these as general guidance and consider discussing them with a qualified clinician."
        )
        return roadmap

    roadmap.safety_status = "GREEN"
    roadmap.next_checkup_days = 14
    return roadmap

