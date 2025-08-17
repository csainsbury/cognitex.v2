from enum import Enum
from typing import Any, Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

class MessageType(str, Enum):
    """Types of messages that can be sent between agents"""
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    STATUS = "status"

class MessagePriority(str, Enum):
    """Priority levels for message processing"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class Message(BaseModel):
    """
    Core message structure for inter-agent communication.
    All agent communication happens through Message objects.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    sender: str  # Agent name or system component
    recipient: Optional[str] = None  # None for broadcast
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None  # For tracking related messages
    reply_to: Optional[str] = None  # ID of message being replied to
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def create_reply(self, 
                    sender: str,
                    payload: Dict[str, Any],
                    type: Optional[MessageType] = None) -> "Message":
        """Create a reply message to this message"""
        return Message(
            type=type or MessageType.RESPONSE,
            sender=sender,
            recipient=self.sender,
            payload=payload,
            priority=self.priority,
            correlation_id=self.correlation_id or self.id,
            reply_to=self.id
        )
    
    def create_error_reply(self,
                          sender: str,
                          error: str,
                          details: Optional[Dict[str, Any]] = None) -> "Message":
        """Create an error reply to this message"""
        payload = {"error": error}
        if details:
            payload["details"] = details
        
        return Message(
            type=MessageType.ERROR,
            sender=sender,
            recipient=self.sender,
            payload=payload,
            priority=MessagePriority.HIGH,
            correlation_id=self.correlation_id or self.id,
            reply_to=self.id
        )
    
    def is_broadcast(self) -> bool:
        """Check if this is a broadcast message"""
        return self.recipient is None
    
    def is_error(self) -> bool:
        """Check if this is an error message"""
        return self.type == MessageType.ERROR
    
    def is_response_to(self, message_id: str) -> bool:
        """Check if this message is a response to a specific message"""
        return self.reply_to == message_id
    
    def __str__(self) -> str:
        return f"Message(id={self.id}, type={self.type}, sender={self.sender}, recipient={self.recipient})"