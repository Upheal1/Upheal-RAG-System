"""
Director Evaluator — Analyzes user interaction patterns to determine mutation triggers.

The evaluator is the first stage of the Director self-correction loop:
1. Evaluator: Analyzes telemetry and decides IF mutation is needed
2. Mutation Engine: Executes the mutation and records audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from services.shared.logging import get_logger

logger = get_logger(__name__)


class MutationTrigger(str, Enum):
    """Types of mutation triggers detected by the evaluator."""

    HIGH_DROP_OFF = "high_drop_off"
    LOW_COMPLETION = "low_completion"
    SKILL_STUCK = "skill_stuck"
    XP_IMBALANCE = "xp_imbalance"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    SAFETY_ESCALATION = "safety_escalation"


class MutationSeverity(str, Enum):
    """Severity levels for mutation recommendations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InteractionMetrics:
    """Aggregated metrics for a user's task interactions."""

    total_interactions: int = 0
    completions: int = 0
    skips: int = 0
    starts: int = 0
    views: int = 0
    avg_completion_time: float = 0.0
    avg_drop_off_point: float = 0.0
    tasks_by_difficulty: Dict[int, int] = field(default_factory=dict)
    tasks_by_tag: Dict[str, int] = field(default_factory=dict)
    recent_ratings: List[int] = field(default_factory=list)
    frustration_signals: int = 0

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate (0.0 to 1.0)."""
        if self.total_interactions == 0:
            return 0.0
        return self.completions / self.total_interactions

    @property
    def skip_rate(self) -> float:
        """Calculate skip rate (0.0 to 1.0)."""
        if self.total_interactions == 0:
            return 0.0
        return self.skips / self.total_interactions

    @property
    def avg_rating(self) -> Optional[float]:
        """Calculate average user rating if available."""
        if not self.recent_ratings:
            return None
        return sum(self.recent_ratings) / len(self.recent_ratings)


@dataclass
class MutationRecommendation:
    """Recommendation for a roadmap mutation."""

    trigger: MutationTrigger
    severity: MutationSeverity
    rationale: str
    confidence: float  # 0.0 to 1.0
    affected_user_id: UUID
    suggested_action: str
    suggested_difficulty_cap: Optional[int] = None
    suggested_tag_focus: List[str] = field(default_factory=list)
    xp_multiplier_adjustment: Optional[float] = None


@dataclass
class EvaluationResult:
    """Complete evaluation result for a user."""

    user_id: UUID
    evaluated_at: datetime
    metrics: InteractionMetrics
    recommendations: List[MutationRecommendation] = field(default_factory=list)
    should_mutate: bool = False
    primary_trigger: Optional[MutationTrigger] = None


class Thresholds:
    """Configuration thresholds for mutation detection."""

    # Completion rate thresholds
    COMPLETION_LOW = 0.3
    COMPLETION_CRITICAL = 0.15

    # Skip rate thresholds
    SKIP_HIGH = 0.5
    SKIP_CRITICAL = 0.7

    # Drop-off thresholds
    DROPOFF_HIGH = 0.6
    DROPOFF_CRITICAL = 0.8

    # Rating thresholds
    RATING_LOW = 2.5
    RATING_CRITICAL = 2.0

    # Frustration signal threshold
    FRUSTRATION_LIMIT = 3

    # Time window for analysis (days)
    ANALYSIS_WINDOW_DAYS = 7

    # Minimum interactions for evaluation
    MIN_INTERACTIONS = 5


class DirectorEvaluator:
    """
    Evaluates user interaction patterns to determine mutation needs.

    The evaluator queries interaction_logs and other telemetry to:
    1. Aggregate interaction metrics over a time window
    2. Detect patterns indicating roadmap mismatch
    3. Generate mutation recommendations with confidence scores
    4. Determine if mutation threshold is crossed
    """

    def __init__(self, supabase_client=None):
        self._client = supabase_client
        self.thresholds = Thresholds()

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from services.shared.state import SupabaseSyncHook

            # Use the hook's client building logic
            hook = SupabaseSyncHook("interaction_logs")
            self._client = hook.client
        return self._client

    def evaluate_user(
        self,
        user_id: UUID,
        lookback_days: int = None,
    ) -> EvaluationResult:
        """
        Evaluate a user's interaction patterns for mutation triggers.

        Parameters
        ----------
        user_id : UUID
            User to evaluate
        lookback_days : int, optional
            Number of days to look back (default: Thresholds.ANALYSIS_WINDOW_DAYS)

        Returns
        -------
        EvaluationResult
            Complete evaluation with metrics and recommendations
        """
        lookback = lookback_days or self.thresholds.ANALYSIS_WINDOW_DAYS
        since = datetime.now(timezone.utc) - timedelta(days=lookback)

        logger.info(
            "director.evaluator.start",
            user_id=str(user_id),
            lookback_days=lookback,
        )

        # Aggregate metrics
        metrics = self._aggregate_metrics(user_id, since)

        # Generate recommendations based on metrics
        recommendations = self._analyze_patterns(user_id, metrics)

        # Determine if mutation is needed
        should_mutate = len(recommendations) > 0
        primary_trigger = recommendations[0].trigger if recommendations else None

        result = EvaluationResult(
            user_id=user_id,
            evaluated_at=datetime.now(timezone.utc),
            metrics=metrics,
            recommendations=recommendations,
            should_mutate=should_mutate,
            primary_trigger=primary_trigger,
        )

        logger.info(
            "director.evaluator.complete",
            user_id=str(user_id),
            should_mutate=should_mutate,
            recommendation_count=len(recommendations),
            completion_rate=round(metrics.completion_rate, 2),
            skip_rate=round(metrics.skip_rate, 2),
        )

        return result

    def _aggregate_metrics(
        self,
        user_id: UUID,
        since: datetime,
    ) -> InteractionMetrics:
        """
        Aggregate interaction metrics from the database.

        Queries interaction_logs for the user within the time window
        and calculates completion rates, drop-off patterns, etc.
        """
        try:
            response = (
                self.client.table("interaction_logs")
                .select("*")
                .eq("user_id", str(user_id))
                .gte("recorded_at", since.isoformat())
                .execute()
            )

            logs = response.data or []

            if not logs:
                logger.info(
                    "director.evaluator.no_logs",
                    user_id=str(user_id),
                )
                return InteractionMetrics()

            metrics = InteractionMetrics(total_interactions=len(logs))

            completion_times = []
            drop_off_points = []

            for log in logs:
                interaction_type = log.get("interaction_type", "").upper()

                if interaction_type == "COMPLETED":
                    metrics.completions += 1
                elif interaction_type == "SKIPPED":
                    metrics.skips += 1
                elif interaction_type == "STARTED":
                    metrics.starts += 1
                elif interaction_type == "VIEWED":
                    metrics.views += 1

                # Collect completion times
                if log.get("completion_time"):
                    completion_times.append(log["completion_time"])

                # Collect drop-off points
                if log.get("drop_off_point") is not None:
                    drop_off_points.append(log["drop_off_point"])

                # Collect ratings
                if log.get("user_rating"):
                    metrics.recent_ratings.append(log["user_rating"])

                # Detect frustration signals (quick skips after starting)
                if interaction_type == "SKIPPED" and log.get("completion_time", 0) < 30:
                    metrics.frustration_signals += 1

            # Calculate averages
            if completion_times:
                metrics.avg_completion_time = sum(completion_times) / len(completion_times)

            if drop_off_points:
                metrics.avg_drop_off_point = sum(drop_off_points) / len(drop_off_points)

            logger.info(
                "director.evaluator.metrics_aggregated",
                user_id=str(user_id),
                total_logs=len(logs),
                completion_rate=round(metrics.completion_rate, 2),
                avg_drop_off=round(metrics.avg_drop_off_point, 2),
            )

            return metrics

        except Exception as e:
            logger.error(
                "director.evaluator.aggregation_error",
                user_id=str(user_id),
                error=str(e),
            )
            return InteractionMetrics()

    def _analyze_patterns(
        self,
        user_id: UUID,
        metrics: InteractionMetrics,
    ) -> List[MutationRecommendation]:
        """
        Analyze metrics and generate mutation recommendations.

        Checks various thresholds and patterns to determine if
        roadmap mutations are needed.
        """
        recommendations = []

        # Skip if not enough data
        if metrics.total_interactions < self.thresholds.MIN_INTERACTIONS:
            logger.info(
                "director.evaluator.insufficient_data",
                user_id=str(user_id),
                interactions=metrics.total_interactions,
                min_required=self.thresholds.MIN_INTERACTIONS,
            )
            return recommendations

        # Check for low completion rate
        if metrics.completion_rate < self.thresholds.COMPLETION_CRITICAL:
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.LOW_COMPLETION,
                    severity=MutationSeverity.CRITICAL,
                    rationale=(
                        f"Critical low completion rate: {metrics.completion_rate:.1%}. "
                        f"User is struggling with current roadmap difficulty."
                    ),
                    confidence=0.9,
                    affected_user_id=user_id,
                    suggested_action="DOWNGRADE_PIVOT",
                    suggested_difficulty_cap=2,
                    suggested_tag_focus=["grounding", "breathing"],
                )
            )
        elif metrics.completion_rate < self.thresholds.COMPLETION_LOW:
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.LOW_COMPLETION,
                    severity=MutationSeverity.HIGH,
                    rationale=(
                        f"Low completion rate: {metrics.completion_rate:.1%}. "
                        f"Consider reducing difficulty or changing task types."
                    ),
                    confidence=0.75,
                    affected_user_id=user_id,
                    suggested_action="DOWNGRADE_PIVOT",
                    suggested_difficulty_cap=3,
                )
            )

        # Check for high skip rate
        if metrics.skip_rate > self.thresholds.SKIP_CRITICAL:
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.HIGH_DROP_OFF,
                    severity=MutationSeverity.HIGH,
                    rationale=(
                        f"Critical skip rate: {metrics.skip_rate:.1%}. "
                        f"Tasks may be mismatched to user preferences."
                    ),
                    confidence=0.85,
                    affected_user_id=user_id,
                    suggested_action="RETRIEVAL_REWEIGHT",
                    suggested_tag_focus=["anxiety", "depression"],
                )
            )

        # Check for high drop-off
        if metrics.avg_drop_off_point > self.thresholds.DROPOFF_HIGH:
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.HIGH_DROP_OFF,
                    severity=MutationSeverity.MEDIUM,
                    rationale=(
                        f"High average drop-off at {metrics.avg_drop_off_point:.1%}. "
                        f"Tasks may be too long or complex."
                    ),
                    confidence=0.7,
                    affected_user_id=user_id,
                    suggested_action="DOWNGRADE_PIVOT",
                    suggested_difficulty_cap=3,
                )
            )

        # Check for low ratings
        avg_rating = metrics.avg_rating
        if avg_rating is not None and avg_rating < self.thresholds.RATING_LOW:
            severity = (
                MutationSeverity.HIGH
                if avg_rating < self.thresholds.RATING_CRITICAL
                else MutationSeverity.MEDIUM
            )
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.SKILL_STUCK,
                    severity=severity,
                    rationale=(
                        f"Low average rating: {avg_rating:.1f}/5. "
                        f"User satisfaction indicates roadmap mismatch."
                    ),
                    confidence=0.8,
                    affected_user_id=user_id,
                    suggested_action="PROMOTION",
                    suggested_tag_focus=["mindfulness", "relaxation"],
                )
            )

        # Check for frustration signals
        if metrics.frustration_signals >= self.thresholds.FRUSTRATION_LIMIT:
            recommendations.append(
                MutationRecommendation(
                    trigger=MutationTrigger.FRUSTRATION_SIGNAL,
                    severity=MutationSeverity.HIGH,
                    rationale=(
                        f"Detected {metrics.frustration_signals} frustration signals "
                        f"(quick skips). Immediate intervention needed."
                    ),
                    confidence=0.85,
                    affected_user_id=user_id,
                    suggested_action="EMERGENCY_OVERRIDE",
                    suggested_difficulty_cap=1,
                    suggested_tag_focus=["grounding", "breathing"],
                    xp_multiplier_adjustment=2.0,
                )
            )

        # Sort by severity (critical first)
        severity_order = {
            MutationSeverity.CRITICAL: 0,
            MutationSeverity.HIGH: 1,
            MutationSeverity.MEDIUM: 2,
            MutationSeverity.LOW: 3,
        }
        recommendations.sort(key=lambda r: severity_order.get(r.severity, 4))

        return recommendations

    def batch_evaluate(
        self,
        user_ids: List[UUID],
        lookback_days: int = None,
    ) -> Dict[UUID, EvaluationResult]:
        """
        Evaluate multiple users in batch.

        Parameters
        ----------
        user_ids : List[UUID]
            Users to evaluate
        lookback_days : int, optional
            Analysis window (default: Thresholds.ANALYSIS_WINDOW_DAYS)

        Returns
        -------
        Dict[UUID, EvaluationResult]
            Mapping of user_id to evaluation result
        """
        results = {}
        for user_id in user_ids:
            try:
                result = self.evaluate_user(user_id, lookback_days)
                results[user_id] = result
            except Exception as e:
                logger.error(
                    "director.evaluator.batch_error",
                    user_id=str(user_id),
                    error=str(e),
                )
        return results


def create_evaluator(supabase_client=None) -> DirectorEvaluator:
    """Factory function to create a DirectorEvaluator."""
    return DirectorEvaluator(supabase_client=supabase_client)
