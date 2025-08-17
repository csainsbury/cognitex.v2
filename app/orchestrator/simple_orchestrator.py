import asyncio
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
import logging
from datetime import datetime

from .message import Message, MessageType, MessagePriority

logger = logging.getLogger(__name__)

class SimpleOrchestrator:
    """
    Simple synchronous orchestrator for managing agent communication.
    This is a basic implementation that will be enhanced with async capabilities later.
    """
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}  # agent_name -> agent_instance
        self.message_queue: List[Message] = []
        self.message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.running = False
        self.processed_count = 0
        self.error_count = 0
        
    def register_agent(self, name: str, agent: Any) -> None:
        """Register an agent with the orchestrator"""
        if name in self.agents:
            logger.warning(f"Agent {name} already registered, replacing")
        
        self.agents[name] = agent
        logger.info(f"Registered agent: {name}")
        
    def unregister_agent(self, name: str) -> None:
        """Unregister an agent from the orchestrator"""
        if name in self.agents:
            del self.agents[name]
            logger.info(f"Unregistered agent: {name}")
        else:
            logger.warning(f"Attempted to unregister unknown agent: {name}")
    
    def get_agent(self, name: str) -> Optional[Any]:
        """Get an agent by name"""
        return self.agents.get(name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names"""
        return list(self.agents.keys())
    
    def send_message(self, message: Message) -> None:
        """
        Send a message to be processed by the orchestrator.
        Messages are queued and processed based on priority.
        """
        self.message_queue.append(message)
        # Sort by priority (critical first) and timestamp
        self.message_queue.sort(
            key=lambda m: (
                -self._priority_value(m.priority),
                m.timestamp
            )
        )
        logger.debug(f"Queued message: {message}")
    
    def broadcast_message(self, message: Message) -> None:
        """Broadcast a message to all agents"""
        message.recipient = None  # Ensure it's a broadcast
        self.send_message(message)
        logger.info(f"Broadcasting message from {message.sender}")
    
    async def send_and_wait(self, message: Message, timeout: float = 30.0) -> Optional[Message]:
        """
        Send a message and wait for a response.
        This enables synchronous-style communication while maintaining the message-based architecture.
        
        Args:
            message: The message to send
            timeout: Maximum time to wait for response in seconds
            
        Returns:
            Response message if received, None if timeout
        """
        # Create a future to wait for the response
        response_future = asyncio.Future()
        request_id = message.id
        
        # Store the future indexed by request ID
        if not hasattr(self, '_pending_responses'):
            self._pending_responses = {}
        self._pending_responses[request_id] = response_future
        
        # Send the message
        self.send_message(message)
        
        try:
            # Process the message immediately if not running in background
            if not self.running:
                response = await self.process_message(message)
                if response:
                    return response
            else:
                # Wait for response with timeout
                response = await asyncio.wait_for(response_future, timeout=timeout)
                return response
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to message {request_id}")
            return None
        finally:
            # Clean up the pending response tracker
            if request_id in self._pending_responses:
                del self._pending_responses[request_id]
    
    async def process_message(self, message: Message) -> Optional[Message]:
        """
        Process a single message.
        Returns a response message if applicable.
        """
        try:
            # Handle broadcast messages
            if message.is_broadcast():
                responses = []
                for agent_name, agent in self.agents.items():
                    if agent_name != message.sender:  # Don't send to sender
                        try:
                            if hasattr(agent, 'handle_message'):
                                response = await agent.handle_message(message)
                                if response:
                                    responses.append(response)
                        except Exception as e:
                            logger.error(f"Agent {agent_name} failed to handle broadcast: {e}")
                return None  # Broadcasts don't return a single response
            
            # Handle targeted messages
            if message.recipient:
                agent = self.agents.get(message.recipient)
                if not agent:
                    logger.error(f"Unknown recipient: {message.recipient}")
                    return message.create_error_reply(
                        sender="orchestrator",
                        error=f"Unknown agent: {message.recipient}"
                    )
                
                if hasattr(agent, 'handle_message'):
                    response = await agent.handle_message(message)
                    self.processed_count += 1
                    return response
                else:
                    logger.error(f"Agent {message.recipient} cannot handle messages")
                    return message.create_error_reply(
                        sender="orchestrator",
                        error=f"Agent {message.recipient} cannot handle messages"
                    )
            
            # No recipient specified and not broadcast
            logger.warning(f"Message has no recipient and is not broadcast: {message}")
            return None
            
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            self.error_count += 1
            return message.create_error_reply(
                sender="orchestrator",
                error=str(e)
            )
    
    async def process_queue(self) -> None:
        """Process all queued messages"""
        while self.message_queue:
            message = self.message_queue.pop(0)
            response = await self.process_message(message)
            if response:
                self.send_message(response)
    
    async def run(self, process_interval: float = 0.1) -> None:
        """
        Run the orchestrator processing loop.
        This processes messages from the queue at regular intervals.
        """
        self.running = True
        logger.info("Orchestrator started")
        
        try:
            while self.running:
                if self.message_queue:
                    await self.process_queue()
                await asyncio.sleep(process_interval)
        except asyncio.CancelledError:
            logger.info("Orchestrator cancelled")
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
        finally:
            self.running = False
            logger.info("Orchestrator stopped")
    
    def stop(self) -> None:
        """Stop the orchestrator"""
        self.running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            "agents_registered": len(self.agents),
            "messages_queued": len(self.message_queue),
            "messages_processed": self.processed_count,
            "errors": self.error_count,
            "running": self.running
        }
    
    def _priority_value(self, priority: MessagePriority) -> int:
        """Convert priority to numeric value for sorting"""
        priority_map = {
            MessagePriority.LOW: 0,
            MessagePriority.NORMAL: 1,
            MessagePriority.HIGH: 2,
            MessagePriority.CRITICAL: 3
        }
        return priority_map.get(priority, 1)