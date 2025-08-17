#!/usr/bin/env python3
"""
Script to manually trigger synthesis for testing
"""
import asyncio
import logging
from datetime import datetime, timedelta
from app.agents.proactive_synthesis_agent import ProactiveSynthesisAgent
from app.orchestrator import SimpleOrchestrator
from app.orchestrator.message import Message, MessageType, MessagePriority
from app.agents.email_agent import EmailAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def trigger_synthesis():
    """Trigger a synthesis cycle for testing"""
    
    # Initialize Firebase
    from app.database.firebase_client import firebase_client
    try:
        firebase_client.initialize()
        logger.info("Firebase initialized")
    except Exception as e:
        logger.warning(f"Firebase initialization failed: {e}")
    
    # Initialize orchestrator and agents
    orchestrator = SimpleOrchestrator()
    
    # Register agents
    email_agent = EmailAgent()
    synthesis_agent = ProactiveSynthesisAgent()
    
    orchestrator.register_agent(email_agent.name, email_agent)
    orchestrator.register_agent(synthesis_agent.name, synthesis_agent)
    
    logger.info("Initialized orchestrator and agents")
    
    # Create synthesis task message
    # Use a test user ID - you may need to adjust this
    user_id = "111018964196923720973"  # From the logs
    
    message = Message(
        type=MessageType.COMMAND,
        sender="Manual",
        recipient="ProactiveSynthesisAgent",
        payload={
            "action": "START_SYNTHESIS_CYCLE",
            "user_id": user_id,
            "triggered_by": "manual",
            "force": True
        },
        metadata={
            "action": "START_SYNTHESIS_CYCLE",
            "user_id": user_id,
            "triggered_by": "manual",
            "force": True
        },
        priority=MessagePriority.HIGH
    )
    
    logger.info(f"Triggering synthesis for user {user_id}")
    
    # Send message to orchestrator
    response = await orchestrator.send_and_wait(message, timeout=60.0)
    
    if response:
        logger.info(f"Synthesis completed: {response.payload}")
    else:
        logger.warning("Synthesis timed out or failed")
    
    # Stop orchestrator
    orchestrator.stop()
    
    return response

if __name__ == "__main__":
    result = asyncio.run(trigger_synthesis())
    if result:
        print("\nSynthesis completed successfully!")
        print(f"Result: {result.payload}")
    else:
        print("\nSynthesis failed or timed out")