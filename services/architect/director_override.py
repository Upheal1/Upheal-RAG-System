"""
Director override loader for pipeline integration.

Loads active MutationInstruction from Supabase and applies constraints
to the RetrievalQuery before candidate retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from services.shared.logging import get_logger
from services.shared.schemas import RetrievalQuery

logger = get_logger(__name__)


@dataclass
class DirectorDirective:
    """Active mutation instruction from the Director."""

    directive_id: UUID
    user_id: UUID
    max_difficulty: Optional[int] = None
    xp_multiplier: Optional[float] = None
    tag_focus: List[str] = None
    valid_until: Optional[datetime] = None

    def __post_init__(self):
        if self.tag_focus is None:
            self.tag_focus = []

    def is_expired(self) -> bool:
        """Check if directive has expired."""
        if self.valid_until is None:
            return False

        if isinstance(self.valid_until, str):
            try:
                parsed = self.valid_until.replace("Z", "+00:00")
                self.valid_until = datetime.fromisoformat(parsed)
            except (ValueError, AttributeError):
                return False

        now = datetime.now(timezone.utc)
        return now > self.valid_until


def _parse_directive_from_row(row: dict) -> Optional[DirectorDirective]:
    """Parse a database row into DirectorDirective."""
    if not row:
        return None

    try:
        post_state = row.get("post_mutation_state", {})
        retrieval_overrides = row.get("retrieval_overrides", {})

        directive = DirectorDirective(
            directive_id=UUID(row["directive_id"]),
            user_id=UUID(row["user_id"]),
            max_difficulty=retrieval_overrides.get("max_difficulty"),
            xp_multiplier=retrieval_overrides.get("xp_multiplier"),
            tag_focus=retrieval_overrides.get("tag_focus", []),
            valid_until=row.get("valid_until"),
        )

        if directive.is_expired():
            logger.info(
                "architect.director_override.expired",
                directive_id=str(directive.directive_id),
                valid_until=str(directive.valid_until),
            )
            return None

        return directive

    except (KeyError, ValueError, TypeError) as e:
        logger.warning(
            "architect.director_override.parse_error",
            error=str(e),
            row_keys=list(row.keys()) if row else [],
        )
        return None


def load_active_directive(
    user_id: str,
    supabase_client=None,
) -> Optional[DirectorDirective]:
    """
    Load the active Director directive for a user.

    Queries roadmap_mutations for the most recent non-expired directive.
    Returns None if no active directive exists.

    Parameters
    ----------
    user_id : str
        User UUID as string.
    supabase_client : optional
        Supabase client for testing. If None, uses state.py SupabaseSyncHook.

    Returns
    -------
    Optional[DirectorDirective]
        Active directive or None.
    """
    try:
        user_uuid = UUID(user_id)
    except (ValueError, AttributeError):
        logger.warning(
            "architect.director_override.invalid_user_id",
            user_id=user_id,
        )
        return None

    logger.info(
        "architect.director_override.load_start",
        user_id=str(user_uuid),
    )

    try:
        if supabase_client is not None:
            return _load_from_client(supabase_client, user_uuid)
        else:
            return _load_from_state(user_uuid)
    except Exception as e:
        logger.warning(
            "architect.director_override.load_error",
            user_id=str(user_uuid),
            error=str(e),
        )
        return None


def _load_from_client(client, user_uuid: UUID) -> Optional[DirectorDirective]:
    """Load directive using provided client."""
    now = datetime.now(timezone.utc)

    response = (
        client.table("roadmap_mutations")
        .select("*")
        .eq("user_id", str(user_uuid))
        .order("triggered_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        logger.info(
            "architect.director_override.no_active",
            user_id=str(user_uuid),
        )
        return None

    directive = _parse_directive_from_row(response.data[0])
    if directive and directive.is_expired():
        return None
    return directive


def _load_from_state(user_uuid: UUID) -> Optional[DirectorDirective]:
    """Load directive using SupabaseSyncHook from state.py."""
    from services.shared.state import SupabaseSyncHook

    hook = SupabaseSyncHook("roadmap_mutations")
    now = datetime.now(timezone.utc).isoformat()

    row = hook.fetch_one({"user_id": str(user_uuid)})

    if not row:
        return None

    valid_until = row.get("valid_until")
    if valid_until:
        if isinstance(valid_until, str):
            valid_until = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > valid_until:
            return None

    return _parse_directive_from_row(row)


def apply_directive_constraints(
    directive: DirectorDirective,
    query: RetrievalQuery,
) -> RetrievalQuery:
    """
    Apply Director directive constraints to a RetrievalQuery.

    Constraints applied:
    - max_difficulty: Lowered if directive specifies lower limit
    - symptom_keywords: Extended with tag_focus if present

    Parameters
    ----------
    directive : DirectorDirective
        Active directive with constraints.
    query : RetrievalQuery
        Original retrieval query.

    Returns
    -------
    RetrievalQuery
        Modified query with constraints applied.
    """
    original_max = query.max_difficulty
    original_keywords = list(query.symptom_keywords)

    if directive.max_difficulty is not None:
        query.max_difficulty = min(query.max_difficulty, directive.max_difficulty)
        logger.info(
            "architect.director_override.max_difficulty_applied",
            original=original_max,
            new=query.max_difficulty,
        )

    if directive.tag_focus:
        new_keywords = list(set(original_keywords) | set(directive.tag_focus))
        query.symptom_keywords = new_keywords
        logger.info(
            "architect.director_override.tag_focus_applied",
            original=original_keywords,
            new=new_keywords,
        )

    logger.info(
        "architect.director_override.constraints_applied",
        directive_id=str(directive.directive_id),
        max_difficulty=query.max_difficulty,
        symptom_keywords=query.symptom_keywords,
    )

    return query
