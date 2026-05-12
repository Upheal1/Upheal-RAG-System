"""
Roadmap API router for fetching user roadmaps.

Endpoints:
    GET /api/roadmap/{user_id}           - Get current roadmap
    GET /api/roadmap/{user_id}/history   - Get roadmap history
    PATCH /api/roadmap/{roadmap_id}/tasks/{task_id} - Update task status
"""

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from services.gateway.auth_middleware import AuthenticatedUser, get_current_user
from services.gateway.schemas import RoadmapResponse
from services.shared.logging import get_logger
from services.shared.schemas import ClinicalTask
from services.shared.state import SupabaseSyncHook

logger = get_logger(__name__)

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class RoadmapHistoryResponse(BaseModel):
    """Response for roadmap history."""
    
    roadmaps: List[RoadmapResponse]
    total_count: int


class TaskStatusUpdate(BaseModel):
    """Request to update task status."""
    
    status: Literal["ASSIGNED", "IN_PROGRESS", "COMPLETED", "SKIPPED"]
    completed_at: Optional[str] = None


def _row_to_roadmap_response(row: dict) -> RoadmapResponse:
    """Convert database row to RoadmapResponse."""
    # Parse suggested_tasks from JSON or reconstruct from roadmap_tasks
    suggested_tasks = []
    
    return RoadmapResponse(
        user_id=row.get("user_id", ""),
        overview_paragraph=row.get("overall_theme", ""),
        suggested_tasks=suggested_tasks,
        safety_status="GREEN",  # Default or extract from data
        next_checkup_days=14,
        generated_at=row.get("generated_at", ""),
        session_id=None,
    )


@router.get(
    "/{user_id}",
    response_model=RoadmapResponse,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Roadmap not found"},
    },
)
async def get_current_roadmap(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapResponse:
    """
    Get the current active roadmap for a user.
    
    Returns the most recent ACTIVE roadmap for the user.
    
    Parameters:
        user_id: User UUID (must match authenticated user or be admin)
    
    Returns:
        Current roadmap
    """
    # Verify user can access this data (users can only access their own)
    if str(current_user.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's roadmap",
        )
    
    try:
        hook = SupabaseSyncHook("roadmaps")
        
        # Get most recent active roadmap
        result = (
            hook.client.table("roadmaps")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "ACTIVE")
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active roadmap found",
            )
        
        roadmap_row = result.data[0]
        roadmap_id = roadmap_row["id"]
        
        # Get associated tasks
        tasks_result = (
            hook.client.table("roadmap_tasks")
            .select("*, clinical_tasks(*)")
            .eq("roadmap_id", roadmap_id)
            .order("sequence_order")
            .execute()
        )
        
        # Convert to ClinicalTask objects
        suggested_tasks = []
        for task_row in tasks_result.data:
            clinical_task = task_row.get("clinical_tasks", {})
            if clinical_task:
                suggested_tasks.append(ClinicalTask(
                    task_id=str(clinical_task.get("id", "")),
                    content=clinical_task.get("description", ""),
                    symptom_tags=clinical_task.get("clinical_tags", []),
                    difficulty=clinical_task.get("difficulty", 1),
                    xp_reward=clinical_task.get("xp_reward", 10),
                    safety_risk=clinical_task.get("safety_risk", False),
                    utility_score=clinical_task.get("utility_score", 0.5),
                    source_reference=clinical_task.get("source_reference", ""),
                    metadata={"roadmap_task_id": task_row.get("id")},
                    phase="Quick Win" if task_row.get("sequence_order", 0) < 2 else "Ladder",
                ))
        
        return RoadmapResponse(
            user_id=user_id,
            overview_paragraph=roadmap_row.get("overall_theme", "Your personalized roadmap"),
            suggested_tasks=suggested_tasks,
            safety_status=roadmap_row.get("status", "GREEN"),
            next_checkup_days=14,
            generated_at=roadmap_row.get("generated_at", ""),
            session_id=None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("roadmap.get.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve roadmap: {e}",
        )


@router.get(
    "/{user_id}/history",
    response_model=RoadmapHistoryResponse,
    responses={401: {"description": "Unauthorized"}},
)
async def get_roadmap_history(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapHistoryResponse:
    """
    Get roadmap history for a user.
    
    Parameters:
        user_id: User UUID
        limit: Maximum number of roadmaps to return
    
    Returns:
        List of past roadmaps
    """
    if str(current_user.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's roadmap history",
        )
    
    try:
        hook = SupabaseSyncHook("roadmaps")
        
        result = (
            hook.client.table("roadmaps")
            .select("*")
            .eq("user_id", user_id)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        
        roadmaps = [_row_to_roadmap_response(row) for row in result.data]
        
        return RoadmapHistoryResponse(
            roadmaps=roadmaps,
            total_count=len(roadmaps),
        )
        
    except Exception as e:
        logger.exception("roadmap.history.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve roadmap history: {e}",
        )


@router.patch(
    "/{roadmap_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Task not found"},
    },
)
async def update_task_status(
    roadmap_id: str,
    task_id: str,
    request: TaskStatusUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """
    Update the status of a roadmap task.
    
    Parameters:
        roadmap_id: Roadmap UUID
        task_id: Roadmap task UUID (not clinical_task ID)
        request: Status update
    
    Returns:
        204 No Content on success
    """
    try:
        hook = SupabaseSyncHook("roadmap_tasks")
        
        # Verify task exists and belongs to user's roadmap
        task_result = (
            hook.client.table("roadmap_tasks")
            .select("*, roadmaps(user_id)")
            .eq("id", task_id)
            .eq("roadmap_id", roadmap_id)
            .execute()
        )
        
        if not task_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        
        task = task_result.data[0]
        if task["roadmaps"]["user_id"] != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify other user's tasks",
            )
        
        # Update status
        update_data = {"status": request.status}
        if request.status == "COMPLETED" and request.completed_at:
            update_data["completed_at"] = request.completed_at
        elif request.status == "COMPLETED":
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        hook.client.table("roadmap_tasks").update(update_data).eq("id", task_id).execute()
        
        logger.info(
            "roadmap.task.status_updated",
            task_id=task_id,
            roadmap_id=roadmap_id,
            status=request.status,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("roadmap.task.update.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task status: {e}",
        )
