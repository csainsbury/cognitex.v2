"""
Email API routes for email agent operations
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.auth import get_current_active_user, UserSession
from app.agents.email_agent import EmailAgent
from app.agents import AgentContext

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/email",
    tags=["email"],
    responses={404: {"description": "Not found"}},
)

# Request models
class EmailSearchRequest(BaseModel):
    """Request model for email search"""
    query: str
    max_results: Optional[int] = 10

class EmailTaskRequest(BaseModel):
    """Request model for email tasks"""
    task: str
    parameters: Optional[Dict[str, Any]] = {}

# Response models
class EmailSummaryResponse(BaseModel):
    """Response model for email summary"""
    success: bool
    summary: Optional[str] = None
    tool_calls: Optional[int] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

# Initialize email agent
email_agent = EmailAgent()

@router.post("/summarize-urgent", response_model=EmailSummaryResponse)
async def summarize_urgent_emails(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Summarize urgent and important emails for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Summary of urgent emails
    """
    try:
        logger.info(f"Summarizing urgent emails for user {current_user.email}")
        
        # Create context
        context = AgentContext(
            user_id=current_user.user_id,
            session_id=current_user.created_at.isoformat(),
            metadata={"task": "summarize_urgent_emails"}
        )
        
        # Process with email agent
        result = await email_agent.process(context)
        
        if result.success:
            data = result.data or {}
            return EmailSummaryResponse(
                success=True,
                summary=data.get("summary"),
                tool_calls=data.get("tool_calls"),
                timestamp=data.get("timestamp")
            )
        else:
            return EmailSummaryResponse(
                success=False,
                error=result.error or "Failed to summarize emails"
            )
            
    except Exception as e:
        logger.error(f"Error summarizing urgent emails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/search", response_model=EmailSummaryResponse)
async def search_emails(
    request: EmailSearchRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Search emails with a custom query.
    
    Args:
        request: Search request with query
        current_user: Current authenticated user
        
    Returns:
        Search results with analysis
    """
    try:
        logger.info(f"Searching emails for user {current_user.email} with query: {request.query}")
        
        # Create context
        context = AgentContext(
            user_id=current_user.user_id,
            session_id=current_user.created_at.isoformat(),
            metadata={
                "task": "search_emails",
                "query": request.query,
                "max_results": request.max_results
            }
        )
        
        # Process with email agent
        result = await email_agent.process(context)
        
        if result.success:
            data = result.data or {}
            return EmailSummaryResponse(
                success=True,
                summary=data.get("analysis"),
                tool_calls=data.get("tool_calls"),
                timestamp=data.get("timestamp")
            )
        else:
            return EmailSummaryResponse(
                success=False,
                error=result.error or "Failed to search emails"
            )
            
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/daily-summary", response_model=EmailSummaryResponse)
async def get_daily_summary(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get daily email summary for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Daily summary of emails
    """
    try:
        logger.info(f"Creating daily summary for user {current_user.email}")
        
        # Create context
        context = AgentContext(
            user_id=current_user.user_id,
            session_id=current_user.created_at.isoformat(),
            metadata={"task": "daily_summary"}
        )
        
        # Process with email agent
        result = await email_agent.process(context)
        
        if result.success:
            data = result.data or {}
            return EmailSummaryResponse(
                success=True,
                summary=data.get("daily_summary"),
                tool_calls=len(data.get("emails_processed", [])),
                timestamp=data.get("timestamp")
            )
        else:
            return EmailSummaryResponse(
                success=False,
                error=result.error or "Failed to create daily summary"
            )
            
    except Exception as e:
        logger.error(f"Error creating daily summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/custom-task", response_model=EmailSummaryResponse)
async def execute_custom_task(
    request: EmailTaskRequest,
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Execute a custom email task.
    
    Args:
        request: Task request with custom instructions
        current_user: Current authenticated user
        
    Returns:
        Task execution result
    """
    try:
        logger.info(f"Executing custom task for user {current_user.email}: {request.task}")
        
        # Create context
        context = AgentContext(
            user_id=current_user.user_id,
            session_id=current_user.created_at.isoformat(),
            metadata={
                "task": request.task,
                **request.parameters
            }
        )
        
        # Process with email agent
        result = await email_agent.process(context)
        
        if result.success:
            data = result.data or {}
            return EmailSummaryResponse(
                success=True,
                summary=data.get("response"),
                tool_calls=data.get("tool_calls"),
                timestamp=data.get("timestamp")
            )
        else:
            return EmailSummaryResponse(
                success=False,
                error=result.error or "Failed to execute task"
            )
            
    except Exception as e:
        logger.error(f"Error executing custom task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/status")
async def get_email_agent_status(
    current_user: UserSession = Depends(get_current_active_user)
):
    """
    Get email agent status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Agent status information
    """
    return {
        "agent": email_agent.name,
        "status": email_agent.status.value,
        "capabilities": list(email_agent.capabilities),
        "run_count": email_agent.run_count,
        "error_count": email_agent.error_count,
        "last_run": email_agent.last_run.isoformat() if email_agent.last_run else None
    }