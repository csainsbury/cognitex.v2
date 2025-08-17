from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import logging
import asyncio
from pydantic import BaseModel, Field

from app.orchestrator.message import Message, MessageType

logger = logging.getLogger(__name__)

class AgentStatus(str, Enum):
    """Status of an agent"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPED = "stopped"

class AgentContext(BaseModel):
    """Context passed to agents during processing"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentResult(BaseModel):
    """Result returned by agents after processing"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Agents are the core processing units that perform specific tasks.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = AgentStatus.IDLE
        self.tools: List[Any] = []  # Tools this agent can use
        self.capabilities: Set[str] = set()  # What this agent can do
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self._lock = asyncio.Lock()
        
    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResult:
        """
        Main processing method that must be implemented by all agents.
        This is where the agent's core logic resides.
        """
        pass
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """
        Handle incoming messages from the orchestrator.
        Default implementation processes the message and returns a response.
        """
        try:
            # Extract context from message
            context = AgentContext(
                user_id=message.metadata.get("user_id"),
                session_id=message.metadata.get("session_id"),
                request_id=message.id,
                metadata=message.metadata
            )
            
            # Process based on message type
            if message.type == MessageType.COMMAND:
                return await self._handle_command(message, context)
            elif message.type == MessageType.QUERY:
                return await self._handle_query(message, context)
            elif message.type == MessageType.EVENT:
                return await self._handle_event(message, context)
            else:
                logger.warning(f"Agent {self.name} received unsupported message type: {message.type}")
                return None
                
        except Exception as e:
            logger.error(f"Agent {self.name} error handling message: {e}")
            return message.create_error_reply(
                sender=self.name,
                error=str(e)
            )
    
    async def _handle_command(self, message: Message, context: AgentContext) -> Message:
        """Handle command messages"""
        async with self._lock:
            self.status = AgentStatus.PROCESSING
            start_time = datetime.utcnow()
            
            try:
                result = await self.process(context)
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                result.processing_time_ms = processing_time
                
                self.last_run = datetime.utcnow()
                self.run_count += 1
                self.status = AgentStatus.IDLE
                
                return message.create_reply(
                    sender=self.name,
                    payload=result.dict()
                )
                
            except Exception as e:
                self.error_count += 1
                self.status = AgentStatus.ERROR
                logger.error(f"Agent {self.name} processing error: {e}")
                
                return message.create_error_reply(
                    sender=self.name,
                    error=str(e)
                )
    
    async def _handle_query(self, message: Message, context: AgentContext) -> Message:
        """Handle query messages - default to command handling"""
        return await self._handle_command(message, context)
    
    async def _handle_event(self, message: Message, context: AgentContext) -> Optional[Message]:
        """Handle event messages - override in subclasses if needed"""
        logger.debug(f"Agent {self.name} received event: {message.payload}")
        return None
    
    def add_tool(self, tool: Any) -> None:
        """Add a tool to this agent's toolbox"""
        self.tools.append(tool)
        logger.debug(f"Added tool to agent {self.name}: {tool}")
    
    def add_capability(self, capability: str) -> None:
        """Add a capability to this agent"""
        self.capabilities.add(capability)
    
    def has_capability(self, capability: str) -> bool:
        """Check if this agent has a specific capability"""
        return capability in self.capabilities
    
    async def initialize(self) -> None:
        """Initialize the agent - override in subclasses if needed"""
        logger.info(f"Initializing agent: {self.name}")
    
    async def shutdown(self) -> None:
        """Shutdown the agent - override in subclasses if needed"""
        logger.info(f"Shutting down agent: {self.name}")
        self.status = AgentStatus.STOPPED
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "name": self.name,
            "status": self.status,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "capabilities": list(self.capabilities),
            "tools_count": len(self.tools)
        }
    
    def __str__(self) -> str:
        return f"Agent({self.name}, status={self.status})"
    
    def __repr__(self) -> str:
        return f"<Agent name='{self.name}' status={self.status} capabilities={self.capabilities}>"