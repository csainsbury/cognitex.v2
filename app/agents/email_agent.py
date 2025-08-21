"""
Email Agent - Handles email-related tasks using LLM reasoning and Gmail tools
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.agents.tools import gmail_tools
from app.services.llm_service import llm_service
from app.services.ai_model_router import ModelComplexity
from app.orchestrator.message import Message, MessageType

logger = logging.getLogger(__name__)

class EmailAgent(BaseAgent):
    """
    Agent that handles email-related tasks using Gmail API and LLM reasoning.
    This agent can search, analyze, and summarize emails based on user requests.
    """
    
    def __init__(self):
        """Initialize the Email Agent"""
        super().__init__(
            name="EmailAgent",
            description="Handles email search, analysis, and summarization tasks"
        )
        
        # Add capabilities
        self.add_capability("search_emails")
        self.add_capability("summarize_emails")
        self.add_capability("find_urgent_emails")
        self.add_capability("analyze_email_patterns")
        
        # Available tools
        self.email_tools = [
            gmail_tools.search_emails,
            gmail_tools.get_email_details,
            gmail_tools.get_recent_important_emails,
            gmail_tools.get_unread_from_contacts
        ]
    
    async def process(self, context: AgentContext) -> AgentResult:
        """
        Main processing method for email tasks.
        
        Args:
            context: Agent context with user information and request
            
        Returns:
            AgentResult with processed email data
        """
        try:
            # Extract task from context
            task = context.metadata.get("task", "summarize_urgent_emails")
            user_id = context.user_id
            
            if not user_id:
                return AgentResult(
                    success=False,
                    error="User ID is required for email operations"
                )
            
            # Route to appropriate handler
            if task == "summarize_urgent_emails":
                result = await self.summarize_urgent_emails(user_id)
            elif task == "search_emails":
                query = context.metadata.get("query", "is:unread")
                result = await self.search_and_analyze_emails(user_id, query)
            elif task == "daily_summary":
                result = await self.create_daily_summary(user_id)
            elif task == "process_new_emails":
                # New task for structured data extraction
                since_str = context.metadata.get("since")
                since_dt = datetime.fromisoformat(since_str) if since_str else datetime.utcnow() - timedelta(hours=24)
                result = await self.process_new_emails(user_id, since_dt)
                return AgentResult(success=True, data={"processed_emails": result})
            else:
                result = await self.handle_custom_request(user_id, task)
            
            return AgentResult(
                success=True,
                data=result
            )
            
        except Exception as e:
            import traceback
            logger.error(f"EmailAgent processing error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return AgentResult(
                success=False,
                error=str(e)
            )
    
    async def summarize_urgent_emails(self, user_id: str) -> Dict[str, Any]:
        """
        Find and summarize urgent/important emails.
        
        Args:
            user_id: User identifier
            
        Returns:
            Summary of urgent emails
        """
        logger.info(f"Summarizing urgent emails for user {user_id}")
        
        # Create prompt for LLM with explicit tool usage instructions
        prompt = """You are an email analysis assistant with access to Gmail tools. You must use these tools to complete your task.

AVAILABLE TOOLS:
1. get_recent_important_emails - Fetches recent important emails
2. search_emails - Searches for specific emails by query
3. get_email_details - Gets full details of a specific email
4. get_unread_from_contacts - Gets unread emails from important contacts

TASK WORKFLOW:
Step 1: Use get_recent_important_emails to fetch the last 100-150 emails
Step 2: If you find references to specific topics needing more detail, use search_emails
Step 3: For critical emails, use get_email_details to get full content

ANALYSIS REQUIREMENTS:
After gathering emails, identify what TRULY matters:

1. MEETINGS & SCHEDULING - Consortium meetings, team sessions, calendar items
2. BUSINESS OPPORTUNITIES - Introductions, partnerships, networking opportunities
3. PEOPLE REQUIRING RESPONSES - Emails from individuals awaiting replies
4. PROJECT UPDATES - Work items needing decisions or awareness
5. DEADLINES - Time-sensitive items with specific dates

PRIORITIZATION:
HIGH PRIORITY (urgency 4-5):
- Meeting invitations with specific times
- Emails from known colleagues (Josh, Nelson, etc.)
- Project mentions (GEN-IMPACT, RETFound, etc.)
- Emails explicitly requesting action

LOW PRIORITY (urgency 1-2):
- Marketing emails and newsletters
- Social media notifications
- Promotional content
- Automated notifications

OUTPUT FORMAT:
For each category, provide:
- Sender name
- Email subject
- Required action
- Urgency level (1-5)

State "None found" for empty categories.

Remember: You MUST use the tools to gather email data before providing analysis."""
        
        # Execute LLM with tools
        result = await llm_service.execute_with_tools(
            prompt=prompt,
            tools=self.email_tools,
            user_id=user_id,  # Pass user_id as kwarg for tools
            max_iterations=3
        )
        
        # Handle tool_calls properly
        tool_calls = result.get("tool_calls", 0)
        if not isinstance(tool_calls, int):
            tool_calls = len(result.get("tool_history", []))
        
        return {
            "summary": result.get("final_response", result.get("response", "")),
            "tool_calls": tool_calls,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def search_and_analyze_emails(self, user_id: str, query: str) -> Dict[str, Any]:
        """
        Search for emails and provide analysis.
        
        Args:
            user_id: User identifier
            query: Gmail search query
            
        Returns:
            Search results with analysis
        """
        logger.info(f"Searching emails with query: {query}")
        
        prompt = f"""
        Search for emails matching this query: {query}
        Then analyze the results to:
        1. Identify key themes or topics
        2. Highlight important information
        3. Suggest any required actions
        """
        
        result = await llm_service.execute_with_tools(
            prompt=prompt,
            tools=self.email_tools,
            user_id=user_id,
            max_iterations=3
        )
        
        # Handle tool_calls properly
        tool_calls = result.get("tool_calls", 0)
        if not isinstance(tool_calls, int):
            tool_calls = len(result.get("tool_history", []))
        
        return {
            "query": query,
            "analysis": result.get("final_response", result.get("response", "")),
            "tool_calls": tool_calls,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def create_daily_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Create a daily email summary.
        
        Args:
            user_id: User identifier
            
        Returns:
            Daily summary of emails
        """
        logger.info(f"Creating daily summary for user {user_id}")
        
        prompt = """
        Create a comprehensive daily email summary:
        1. Check for urgent/important emails from the last 24 hours
        2. Identify emails requiring responses
        3. Summarize key updates and information
        4. List any deadlines or time-sensitive items
        
        Format the summary in a clear, actionable way.
        """
        
        result = await llm_service.execute_with_tools(
            prompt=prompt,
            tools=self.email_tools,
            user_id=user_id,
            max_iterations=5
        )
        
        # Handle tool_calls properly
        tool_calls = result.get("tool_calls", 0)
        if not isinstance(tool_calls, int):
            tool_calls = len(result.get("tool_history", []))
        
        return {
            "daily_summary": result.get("final_response", result.get("response", "")),
            "emails_processed": tool_calls,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def process_new_emails(self, user_id: str, since: datetime) -> List[Dict[str, Any]]:
        """
        Fetches new emails since a given timestamp, processes them in batches to extract
        structured data, and returns a list of structured email objects.
        
        Args:
            user_id: User identifier
            since: Datetime to fetch emails after
            
        Returns:
            List of structured email data with extracted information
        """
        logger.info(f"Processing new emails for user {user_id} since {since}")
        
        # Fetch all emails since the given timestamp
        emails = gmail_tools.get_emails_since(user_id, since, max_results=50)
        
        if not emails:
            logger.info("No new emails to process")
            return []
        
        logger.info(f"Processing {len(emails)} emails for structured extraction")
        
        # Process emails in batches for efficiency
        batch_size = 5
        processed_emails = []
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i+batch_size]
            try:
                # Process batch of emails together
                batch_results = await self._process_email_batch(batch)
                processed_emails.extend(batch_results)
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size}: {e}")
                # Fallback to basic info for failed batch
                for email in batch:
                    processed_emails.append({
                        "id": email['id'],
                        "subject": email['subject'],
                        "sender": email['sender'],
                        "date": email['date'],
                        "summary": email['snippet'],
                        "intent": "Unknown",
                        "entities": {
                            "people": [],
                            "companies": [],
                            "projects": []
                        },
                        "commitments": {
                            "tasks_for_me": [],
                            "tasks_for_others": [],
                            "deadlines": []
                        },
                        "sentiment": "neutral",
                        "is_reply_needed": False,
                        "urgency_score": 1,
                        "processing_error": str(e)
                    })
        
        logger.info(f"Completed processing {len(processed_emails)} emails")
        return processed_emails
    
    async def _process_email_batch(self, emails: List[Dict]) -> List[Dict[str, Any]]:
        """
        Process a batch of emails in a single LLM call for efficiency.
        
        Args:
            emails: List of email dictionaries to process
            
        Returns:
            List of structured email data
        """
        # Prepare batch data for LLM
        email_batch = []
        for email in emails:
            email_batch.append({
                "id": email['id'],
                "subject": email['subject'],
                "sender": email['sender'],
                "body_preview": email['body'][:500]  # Limit body for context
            })
        
        # Build prompt for batch processing with JSON output
        prompt = f"""Analyze the following email batch. Prioritize identifying work-related content, project communications, and personal correspondence over marketing/promotional emails.

Emails:
{json.dumps(email_batch, indent=2)}

For each email, provide a JSON object with this EXACT structure:
{{
    "id": "email_id",
    "summary": "A concise, one-sentence summary of the email's core message.",
    "intent": "Classify the sender's primary intent: 'Work Project' | 'Meeting Invitation' | 'Request for Action' | 'Question' | 'Follow-up' | 'Personal' | 'Information Sharing' | 'Newsletter' | 'Marketing/Promotional'",
    "entities": {{
        "people": ["Focus on colleagues, clients, collaborators - not marketing personas"],
        "companies": ["Prioritize work-related organizations"],
        "projects": ["Include specific projects like GEN-IMPACT, research initiatives, work deliverables"]
    }},
    "commitments": {{
        "tasks_for_me": ["Specific action item I need to do."],
        "tasks_for_others": ["Action item someone else was asked to do."],
        "deadlines": ["YYYY-MM-DD: Description of deadline."]
    }},
    "sentiment": "positive | negative | neutral | urgent",
    "is_reply_needed": true | false,
    "urgency_score": 3,
    "is_work_related": true | false,
    "sender_importance": "high | medium | low"
}}

SCORING GUIDELINES:
- urgency_score 5: Critical work deadlines, urgent requests from managers/clients, time-sensitive projects
- urgency_score 4: Important work tasks, scheduled meetings, project updates requiring action
- urgency_score 3: Regular work correspondence, standard follow-ups, collaborative discussions
- urgency_score 2: Personal emails, FYI information, non-urgent updates
- urgency_score 1: Marketing emails, newsletters, promotional content, automated notifications

SENDER IMPORTANCE:
- high: Direct colleagues, managers, clients, key collaborators on active projects
- medium: Extended team members, occasional contacts, service providers
- low: Marketing senders, automated systems, unknown contacts

KEY FOCUS:
- Identify emails mentioning specific projects (GEN-IMPACT, research, deliverables)
- Flag emails requiring responses or actions
- Extract concrete deadlines and commitments
- Distinguish genuine work communication from promotional content

Return ONLY a valid JSON array of these objects. No additional text."""
        
        try:
            # Use SIMPLE model for efficient batch processing
            result = await llm_service.simple_completion(
                prompt=prompt,
                complexity=ModelComplexity.SIMPLE,  # Use complexity instead of hardcoded model
                max_tokens=1500  # More tokens for batch response
            )
            
            # Parse JSON response
            try:
                batch_analysis = json.loads(result.strip())
                
                # Map analysis back to original emails
                processed = []
                for email in emails:
                    # Find matching analysis by ID
                    analysis = next((a for a in batch_analysis if a.get('id') == email['id']), None)
                    
                    if analysis:
                        processed.append({
                            "id": email['id'],
                            "subject": email['subject'],
                            "sender": email['sender'],
                            "date": email['date'],
                            "thread_id": email['threadId'],
                            "has_attachments": email['has_attachments'],
                            "labels": email['labels'],
                            "summary": analysis.get('summary', email['snippet']),
                            "intent": analysis.get('intent', 'Unknown'),
                            "entities": analysis.get('entities', {}),
                            "commitments": analysis.get('commitments', {}),
                            "sentiment": analysis.get('sentiment', 'neutral'),
                            "is_reply_needed": analysis.get('is_reply_needed', False),
                            "urgency_score": analysis.get('urgency_score', 1),
                            "is_work_related": analysis.get('is_work_related', False),
                            "sender_importance": analysis.get('sender_importance', 'low'),
                            "original_body": email['body'][:1000]  # Keep truncated for reference
                        })
                    else:
                        # Fallback if no analysis found
                        processed.append(self._create_fallback_email(email))
                
                return processed
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse batch JSON, using fallback parsing")
                # Fallback to individual processing if JSON fails
                return [self._create_fallback_email(email) for email in emails]
                
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Return basic info for all emails in batch
            return [self._create_fallback_email(email) for email in emails]
    
    def _create_fallback_email(self, email: Dict) -> Dict[str, Any]:
        """Create a fallback email structure when processing fails."""
        return {
            "id": email['id'],
            "subject": email['subject'],
            "sender": email['sender'],
            "date": email['date'],
            "thread_id": email.get('threadId', ''),
            "has_attachments": email.get('has_attachments', False),
            "labels": email.get('labels', []),
            "summary": email.get('snippet', ''),
            "entities": [],
            "tasks": [],
            "sentiment": "neutral",
            "requires_response": False,
            "priority": "low",
            "original_body": email.get('body', '')[:1000]
        }
    
    def _extract_field(self, text: str, field: str, default: str = "") -> str:
        """Extract a specific field from LLM response text."""
        # Simple extraction - could be enhanced with better parsing
        lines = text.lower().split('\n')
        for line in lines:
            if field.lower() in line:
                # Extract the part after the field mention
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return default
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract entities (people, companies, projects) from LLM response."""
        entities = []
        lines = text.split('\n')
        for line in lines:
            if 'entities' in line.lower() or 'people' in line.lower() or 'companies' in line.lower():
                # Extract comma-separated entities
                if ':' in line:
                    entity_text = line.split(':', 1)[1]
                    entities = [e.strip() for e in entity_text.split(',') if e.strip()]
                    break
        return entities
    
    def _extract_tasks(self, text: str) -> List[str]:
        """Extract tasks or action items from LLM response."""
        tasks = []
        lines = text.split('\n')
        for line in lines:
            if 'task' in line.lower() or 'deadline' in line.lower() or 'action' in line.lower():
                if ':' in line:
                    task_text = line.split(':', 1)[1].strip()
                    if task_text and task_text.lower() not in ['none', 'no tasks', 'n/a']:
                        tasks.append(task_text)
        return tasks
    
    def _extract_sentiment(self, text: str) -> str:
        """Extract sentiment from LLM response."""
        text_lower = text.lower()
        if 'positive' in text_lower:
            return 'positive'
        elif 'negative' in text_lower:
            return 'negative'
        return 'neutral'
    
    def _extract_response_needed(self, text: str) -> bool:
        """Determine if email requires a response."""
        text_lower = text.lower()
        return 'response: yes' in text_lower or 'requires response' in text_lower or 'reply needed' in text_lower
    
    def _extract_priority(self, text: str) -> str:
        """Extract priority level from LLM response."""
        text_lower = text.lower()
        if 'priority: high' in text_lower or 'urgent' in text_lower:
            return 'high'
        elif 'priority: medium' in text_lower:
            return 'medium'
        return 'low'
    
    async def handle_custom_request(self, user_id: str, request: str) -> Dict[str, Any]:
        """
        Handle custom email-related requests.
        
        Args:
            user_id: User identifier
            request: Custom request string
            
        Returns:
            Processed result
        """
        logger.info(f"Handling custom request: {request}")
        
        result = await llm_service.execute_with_tools(
            prompt=request,
            tools=self.email_tools,
            user_id=user_id,
            max_iterations=5
        )
        
        return {
            "request": request,
            "response": result["response"],
            "tool_calls": len(result["tool_history"]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def handle_message(self, message: Message) -> Optional[Message]:
        """
        Handle incoming messages from the orchestrator.
        
        Args:
            message: Incoming message
            
        Returns:
            Response message if applicable
        """
        # Extract context from message
        context = AgentContext(
            user_id=message.metadata.get("user_id"),
            session_id=message.metadata.get("session_id"),
            request_id=message.id,
            metadata=message.payload
        )
        
        # Process based on message type
        if message.type == MessageType.COMMAND:
            # Process the command
            result = await self.process(context)
            
            # Create response
            return message.create_reply(
                sender=self.name,
                payload={
                    "success": result.success,
                    "data": result.data if result.success else None,
                    "error": result.error if not result.success else None
                }
            )
        
        return None