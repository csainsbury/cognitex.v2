"""
API routes for goal management
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime

from app.auth import get_current_active_user, UserSession
from app.agents.goal_agent import GoalAgent, GoalType, GoalStatus

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/goals",
    tags=["goals"],
    responses={404: {"description": "Not found"}},
)

# Request/Response models
class CreateGoalRequest(BaseModel):
    """Request model for creating a goal"""
    content: str = Field(..., min_length=1, max_length=500)
    type: GoalType = Field(default=GoalType.SHORT_TERM)
    category: Optional[str] = Field(default="personal", max_length=50)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: Optional[str] = None
    milestones: Optional[List[str]] = []
    notes: Optional[str] = Field(default="", max_length=1000)


class UpdateGoalRequest(BaseModel):
    """Request model for updating a goal"""
    content: Optional[str] = Field(None, min_length=1, max_length=500)
    type: Optional[GoalType] = None
    status: Optional[GoalStatus] = None
    category: Optional[str] = Field(None, max_length=50)
    priority: Optional[int] = Field(None, ge=1, le=5)
    progress: Optional[int] = Field(None, ge=0, le=100)
    target_date: Optional[str] = None
    milestones: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=1000)


class GoalResponse(BaseModel):
    """Response model for a goal"""
    id: str
    content: str
    type: str
    status: str
    category: str
    priority: int
    progress: int
    created_at: str
    updated_at: str
    target_date: Optional[str] = None
    milestones: List[str] = []
    notes: str = ""


class GoalsListResponse(BaseModel):
    """Response model for list of goals"""
    goals: List[GoalResponse]
    count: int
    active_count: int


# Initialize agent
goal_agent = GoalAgent()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    request: CreateGoalRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Create a new goal for the current user.
    
    Args:
        request: Goal creation request
        current_user: Current authenticated user
        
    Returns:
        Created goal
    """
    try:
        from app.agents import AgentContext
        
        context = AgentContext(
            user_id=current_user.user_id,
            metadata={
                "action": "create_goal",
                "content": request.content,
                "type": request.type.value,
                "category": request.category,
                "priority": request.priority,
                "target_date": request.target_date,
                "milestones": request.milestones or [],
                "notes": request.notes
            }
        )
        
        result = await goal_agent.process(context)
        
        if result.success:
            goal = result.data["goal"]
            goal["id"] = result.data["goal_id"]
            return GoalResponse(**goal)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to create goal"
            )
            
    except Exception as e:
        logger.error(f"Failed to create goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=GoalsListResponse)
async def get_goals(
    status_filter: Optional[GoalStatus] = None,
    type_filter: Optional[GoalType] = None,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get all goals for the current user.
    
    Args:
        status_filter: Optional filter by goal status
        type_filter: Optional filter by goal type
        current_user: Current authenticated user
        
    Returns:
        List of user's goals
    """
    try:
        from app.agents import AgentContext
        
        context = AgentContext(
            user_id=current_user.user_id,
            metadata={
                "action": "get_goals",
                "status": status_filter.value if status_filter else None,
                "type": type_filter.value if type_filter else None
            }
        )
        
        result = await goal_agent.process(context)
        
        if result.success:
            goals = [GoalResponse(**goal) for goal in result.data["goals"]]
            return GoalsListResponse(
                goals=goals,
                count=result.data["count"],
                active_count=result.data["active_count"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to retrieve goals"
            )
            
    except Exception as e:
        logger.error(f"Failed to get goals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{goal_id}", response_model=dict)
async def update_goal(
    goal_id: str,
    request: UpdateGoalRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Update an existing goal.
    
    Args:
        goal_id: ID of the goal to update
        request: Update request with new values
        current_user: Current authenticated user
        
    Returns:
        Update confirmation
    """
    try:
        from app.agents import AgentContext
        
        # Build metadata with non-None values
        metadata = {
            "action": "update_goal",
            "goal_id": goal_id
        }
        
        update_dict = request.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                if hasattr(value, 'value'):  # Handle enums
                    metadata[key] = value.value
                else:
                    metadata[key] = value
        
        context = AgentContext(
            user_id=current_user.user_id,
            metadata=metadata
        )
        
        result = await goal_agent.process(context)
        
        if result.success:
            return {
                "success": True,
                "goal_id": result.data["goal_id"],
                "updated_fields": result.data["updated_fields"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to update goal"
            )
            
    except Exception as e:
        logger.error(f"Failed to update goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{goal_id}", response_model=dict)
async def delete_goal(
    goal_id: str,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Delete (archive) a goal.
    
    Args:
        goal_id: ID of the goal to delete
        current_user: Current authenticated user
        
    Returns:
        Deletion confirmation
    """
    try:
        from app.agents import AgentContext
        
        context = AgentContext(
            user_id=current_user.user_id,
            metadata={
                "action": "delete_goal",
                "goal_id": goal_id
            }
        )
        
        result = await goal_agent.process(context)
        
        if result.success:
            return {
                "success": True,
                "message": "Goal archived successfully",
                "goal_id": goal_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to delete goal"
            )
            
    except Exception as e:
        logger.error(f"Failed to delete goal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/analyze-alignment", response_model=dict)
async def analyze_goal_alignment(
    tasks: List[dict],
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Analyze how tasks align with user's goals.
    
    Args:
        tasks: List of tasks to analyze
        current_user: Current authenticated user
        
    Returns:
        Alignment analysis
    """
    try:
        from app.agents import AgentContext
        
        context = AgentContext(
            user_id=current_user.user_id,
            metadata={
                "action": "analyze_alignment",
                "tasks": tasks
            }
        )
        
        result = await goal_agent.process(context)
        
        if result.success:
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to analyze alignment"
            )
            
    except Exception as e:
        logger.error(f"Failed to analyze goal alignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )