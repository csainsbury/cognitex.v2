"""
Goal Management Agent - Manages user goals and objectives
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.database.firebase_client import firebase_client

logger = logging.getLogger(__name__)


class GoalType(str, Enum):
    """Goal time horizons"""
    SHORT_TERM = "short_term"     # < 3 months
    MEDIUM_TERM = "medium_term"   # 3-12 months
    LONG_TERM = "long_term"       # > 12 months


class GoalStatus(str, Enum):
    """Goal completion status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    PAUSED = "paused"


class GoalAgent(BaseAgent):
    """
    Agent responsible for managing user goals and objectives.
    Provides CRUD operations and goal-task alignment analysis.
    """
    
    def __init__(self):
        """Initialize the Goal Agent"""
        super().__init__(
            name="GoalAgent",
            description="Manages user goals and objectives for personalized advice"
        )
        self.add_capability("goal_management")
        self.add_capability("goal_alignment_analysis")
    
    async def process(self, context: AgentContext) -> AgentResult:
        """
        Process goal-related requests.
        
        Args:
            context: Agent context containing the action and goal data
            
        Returns:
            AgentResult with operation outcome
        """
        action = context.metadata.get("action")
        user_id = context.user_id
        
        if not user_id:
            return AgentResult(
                success=False,
                error="User ID is required for goal operations"
            )
        
        try:
            if action == "create_goal":
                return await self._create_goal(user_id, context.metadata)
            elif action == "get_goals":
                return await self._get_goals(user_id, context.metadata)
            elif action == "update_goal":
                return await self._update_goal(user_id, context.metadata)
            elif action == "delete_goal":
                return await self._delete_goal(user_id, context.metadata)
            elif action == "analyze_alignment":
                return await self._analyze_goal_alignment(user_id, context.metadata)
            else:
                return AgentResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            logger.error(f"Goal operation failed: {e}")
            return AgentResult(
                success=False,
                error=str(e)
            )
    
    async def _create_goal(self, user_id: str, metadata: Dict[str, Any]) -> AgentResult:
        """Create a new goal for the user"""
        try:
            goal_data = {
                "user_id": user_id,
                "content": metadata.get("content", ""),
                "type": metadata.get("type", GoalType.SHORT_TERM.value),
                "status": GoalStatus.ACTIVE.value,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "priority": metadata.get("priority", 3),  # 1-5 scale
                "category": metadata.get("category", "personal"),  # personal, work, health, etc.
                "target_date": metadata.get("target_date"),  # Optional deadline
                "progress": 0,  # 0-100 percentage
                "milestones": metadata.get("milestones", []),  # List of sub-goals
                "notes": metadata.get("notes", "")
            }
            
            # Store in Firestore
            doc_ref = firebase_client.db.collection("user_goals").add(goal_data)
            goal_id = doc_ref[1].id
            
            logger.info(f"Created goal {goal_id} for user {user_id}")
            
            return AgentResult(
                success=True,
                data={
                    "goal_id": goal_id,
                    "goal": goal_data
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create goal: {e}")
            return AgentResult(success=False, error=str(e))
    
    async def _get_goals(self, user_id: str, metadata: Dict[str, Any]) -> AgentResult:
        """Retrieve user's goals"""
        try:
            # Build query
            query = firebase_client.db.collection("user_goals").where("user_id", "==", user_id)
            
            # Filter by status if specified
            status_filter = metadata.get("status")
            if status_filter:
                query = query.where("status", "==", status_filter)
            
            # Filter by type if specified
            type_filter = metadata.get("type")
            if type_filter:
                query = query.where("type", "==", type_filter)
            
            # Get documents
            docs = query.stream()
            
            goals = []
            for doc in docs:
                goal = doc.to_dict()
                goal["id"] = doc.id
                goals.append(goal)
            
            # Sort by priority and creation date
            goals.sort(key=lambda x: (-x.get("priority", 0), x.get("created_at", "")))
            
            logger.info(f"Retrieved {len(goals)} goals for user {user_id}")
            
            return AgentResult(
                success=True,
                data={
                    "goals": goals,
                    "count": len(goals),
                    "active_count": sum(1 for g in goals if g.get("status") == GoalStatus.ACTIVE.value)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve goals: {e}")
            return AgentResult(success=False, error=str(e))
    
    async def _update_goal(self, user_id: str, metadata: Dict[str, Any]) -> AgentResult:
        """Update an existing goal"""
        try:
            goal_id = metadata.get("goal_id")
            if not goal_id:
                return AgentResult(success=False, error="Goal ID is required")
            
            # Get the goal document
            doc_ref = firebase_client.db.collection("user_goals").document(goal_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return AgentResult(success=False, error="Goal not found")
            
            # Verify ownership
            goal_data = doc.to_dict()
            if goal_data.get("user_id") != user_id:
                return AgentResult(success=False, error="Unauthorized")
            
            # Prepare update data
            update_data = {
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Update allowed fields
            allowed_fields = ["content", "type", "status", "priority", "category", 
                            "target_date", "progress", "milestones", "notes"]
            for field in allowed_fields:
                if field in metadata:
                    update_data[field] = metadata[field]
            
            # Update the document
            doc_ref.update(update_data)
            
            logger.info(f"Updated goal {goal_id} for user {user_id}")
            
            return AgentResult(
                success=True,
                data={
                    "goal_id": goal_id,
                    "updated_fields": list(update_data.keys())
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to update goal: {e}")
            return AgentResult(success=False, error=str(e))
    
    async def _delete_goal(self, user_id: str, metadata: Dict[str, Any]) -> AgentResult:
        """Delete a goal (actually archives it)"""
        try:
            goal_id = metadata.get("goal_id")
            if not goal_id:
                return AgentResult(success=False, error="Goal ID is required")
            
            # Archive instead of delete to preserve history
            return await self._update_goal(user_id, {
                "goal_id": goal_id,
                "status": GoalStatus.ARCHIVED.value
            })
            
        except Exception as e:
            logger.error(f"Failed to delete goal: {e}")
            return AgentResult(success=False, error=str(e))
    
    async def _analyze_goal_alignment(
        self, 
        user_id: str, 
        metadata: Dict[str, Any]
    ) -> AgentResult:
        """
        Analyze how current tasks/emails align with user goals.
        This is called by ProactiveSynthesisAgent to provide context.
        """
        try:
            # Get active goals
            goals_result = await self._get_goals(user_id, {"status": GoalStatus.ACTIVE.value})
            if not goals_result.success:
                return goals_result
            
            goals = goals_result.data["goals"]
            tasks = metadata.get("tasks", [])
            
            # Analyze alignment
            alignments = []
            for task in tasks:
                task_text = task.get("content", "").lower()
                aligned_goals = []
                
                for goal in goals:
                    goal_text = goal.get("content", "").lower()
                    
                    # Simple keyword matching - could be enhanced with NLP
                    keywords = goal_text.split()
                    if any(keyword in task_text for keyword in keywords if len(keyword) > 3):
                        aligned_goals.append({
                            "goal_id": goal["id"],
                            "goal_content": goal["content"],
                            "goal_type": goal["type"],
                            "alignment_score": 0.7  # Placeholder - could use better scoring
                        })
                
                if aligned_goals:
                    alignments.append({
                        "task": task,
                        "aligned_goals": aligned_goals
                    })
            
            return AgentResult(
                success=True,
                data={
                    "alignments": alignments,
                    "aligned_task_count": len(alignments),
                    "total_task_count": len(tasks),
                    "alignment_percentage": (len(alignments) / len(tasks) * 100) if tasks else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze goal alignment: {e}")
            return AgentResult(success=False, error=str(e))
    
    async def get_active_goals_for_synthesis(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Helper method for ProactiveSynthesisAgent to get formatted active goals.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active goals formatted for synthesis
        """
        try:
            result = await self._get_goals(user_id, {"status": GoalStatus.ACTIVE.value})
            if result.success:
                goals = result.data["goals"]
                # Format for synthesis prompt
                formatted_goals = []
                for goal in goals[:5]:  # Limit to top 5 for context
                    formatted_goals.append({
                        "content": goal["content"],
                        "type": goal["type"],
                        "priority": goal["priority"],
                        "progress": goal.get("progress", 0),
                        "target_date": goal.get("target_date")
                    })
                return formatted_goals
            return []
        except Exception as e:
            logger.error(f"Failed to get goals for synthesis: {e}")
            return []