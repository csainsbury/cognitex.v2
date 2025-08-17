"""
API routes for synthesis insights
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from app.auth import get_current_active_user, UserSession
from app.agents.proactive_synthesis_agent import ProactiveSynthesisAgent
from app.orchestrator.message import Message, MessageType, MessagePriority

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/insights",
    tags=["insights"],
    responses={404: {"description": "Not found"}},
)

# Request/Response models
class InsightResponse(BaseModel):
    """Response model for insights"""
    id: str
    type: str
    title: str
    content: str
    priority: str
    status: str
    source_data: Optional[dict] = None
    created_at: str
    viewed_at: Optional[str] = None

class InsightsListResponse(BaseModel):
    """Response model for list of insights"""
    insights: list[InsightResponse]
    total: int
    has_new: bool

class MarkViewedRequest(BaseModel):
    """Request model for marking insight as viewed"""
    insight_id: str

class TriggerSynthesisRequest(BaseModel):
    """Request model for manually triggering synthesis"""
    force: bool = False

# Initialize synthesis agent
synthesis_agent = ProactiveSynthesisAgent()

@router.get("/", response_model=InsightsListResponse)
async def get_insights(
    current_user: UserSession = Depends(get_current_active_user),
    limit: int = Query(10, ge=1, le=50),
    include_viewed: bool = Query(False),
    insight_type: Optional[str] = Query(None)
):
    """
    Get recent insights for the current user.
    
    Args:
        limit: Maximum number of insights to return (1-50)
        include_viewed: Whether to include already viewed insights
        insight_type: Filter by insight type (daily_briefing, priority_alert, etc.)
    """
    try:
        # Get insights from synthesis agent
        insights = await synthesis_agent.get_recent_insights(
            user_id=current_user.user_id,
            limit=limit,
            include_viewed=include_viewed
        )
        
        # Filter by type if specified
        if insight_type:
            insights = [i for i in insights if i.get("type") == insight_type]
        
        # Check if there are new insights
        has_new = any(i.get("status") == "new" for i in insights)
        
        # Convert to response format
        insight_responses = []
        for insight in insights:
            insight_responses.append(InsightResponse(
                id=insight.get("id", ""),
                type=insight.get("type", ""),
                title=insight.get("title", ""),
                content=insight.get("content", ""),
                priority=insight.get("priority", "normal"),
                status=insight.get("status", "new"),
                source_data=insight.get("source_data"),
                created_at=insight.get("created_at", ""),
                viewed_at=insight.get("viewed_at")
            ))
        
        return InsightsListResponse(
            insights=insight_responses,
            total=len(insight_responses),
            has_new=has_new
        )
        
    except Exception as e:
        logger.error(f"Failed to get insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mark-viewed")
async def mark_insight_viewed(
    request: MarkViewedRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Mark an insight as viewed.
    """
    try:
        success = await synthesis_agent.mark_insight_viewed(
            insight_id=request.insight_id,
            user_id=current_user.user_id
        )
        
        if success:
            return {"success": True, "message": "Insight marked as viewed"}
        else:
            raise HTTPException(status_code=404, detail="Insight not found")
            
    except Exception as e:
        logger.error(f"Failed to mark insight as viewed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger-synthesis")
async def trigger_synthesis(
    request: TriggerSynthesisRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Manually trigger a synthesis cycle for the current user.
    """
    try:
        from app.main import orchestrator
        
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not available")
        
        # Create synthesis task message
        message = Message(
            type=MessageType.COMMAND,
            sender="API",
            recipient="ProactiveSynthesisAgent",
            payload={
                "action": "START_SYNTHESIS_CYCLE",
                "user_id": current_user.user_id,
                "triggered_by": "manual",
                "force": request.force
            },
            metadata={
                "action": "START_SYNTHESIS_CYCLE",
                "user_id": current_user.user_id,
                "triggered_by": "manual",
                "force": request.force
            },
            priority=MessagePriority.HIGH
        )
        
        # Send to orchestrator
        orchestrator.send_message(message)
        
        logger.info(f"Manually triggered synthesis for user {current_user.user_id}")
        
        return {
            "success": True,
            "message": "Synthesis cycle triggered",
            "user_id": current_user.user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger synthesis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_insight_stats(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get statistics about user's insights.
    """
    try:
        from app.database.firebase_client import firebase_client
        
        # Query insights for user
        insights_ref = firebase_client.db.collection("synthesis_insights")
        user_insights = insights_ref.where("user_id", "==", current_user.user_id)
        
        # Count by status
        new_count = 0
        viewed_count = 0
        total_count = 0
        
        # Count by type
        type_counts = {}
        
        for doc in user_insights.stream():
            insight = doc.to_dict()
            total_count += 1
            
            status = insight.get("status", "new")
            if status == "new":
                new_count += 1
            else:
                viewed_count += 1
            
            insight_type = insight.get("type", "unknown")
            type_counts[insight_type] = type_counts.get(insight_type, 0) + 1
        
        return {
            "total_insights": total_count,
            "new_insights": new_count,
            "viewed_insights": viewed_count,
            "insights_by_type": type_counts,
            "user_id": current_user.user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get insight stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{insight_id}")
async def delete_insight(
    insight_id: str,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Delete a specific insight.
    """
    try:
        from app.database.firebase_client import firebase_client
        
        # Get the insight to verify ownership
        doc_ref = firebase_client.db.collection("synthesis_insights").document(insight_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        insight_data = doc.to_dict()
        if insight_data.get("user_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this insight")
        
        # Delete the insight
        doc_ref.delete()
        
        logger.info(f"Deleted insight {insight_id} for user {current_user.user_id}")
        
        return {"success": True, "message": "Insight deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))