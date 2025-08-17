"""
Proactive Synthesis Agent - Orchestrates periodic information synthesis
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.message import Message, MessageType, MessagePriority
from app.services.llm_service import llm_service
from app.services.ai_model_router import ModelComplexity
from app.database.firebase_client import firebase_client

logger = logging.getLogger(__name__)

class ProactiveSynthesisAgent(BaseAgent):
    """
    Master agent that orchestrates periodic synthesis of information
    from multiple sources to generate actionable insights.
    """
    
    def __init__(self):
        """Initialize the Proactive Synthesis Agent"""
        super().__init__(
            name="ProactiveSynthesisAgent",
            description="Synthesizes information from multiple sources to generate insights"
        )
        self.last_sync_times: Dict[str, datetime] = {}
        self.synthesis_interval = timedelta(minutes=15)
        
    async def process(self, context: AgentContext) -> AgentResult:
        """
        Process synthesis requests.
        
        Args:
            context: Agent execution context
            
        Returns:
            AgentResult with synthesis outcomes
        """
        # Get action from metadata (populated from message payload)
        action = context.metadata.get("action")
        
        if action == "START_SYNTHESIS_CYCLE":
            return await self._run_synthesis_cycle(context)
        
        return AgentResult(
            success=False,
            error="Unknown action for ProactiveSynthesisAgent"
        )
    
    async def _run_synthesis_cycle(self, context: AgentContext) -> AgentResult:
        """
        Run a complete synthesis cycle.
        
        This method:
        1. Gathers new information from various agents
        2. Synthesizes the information using AI
        3. Generates insights (daily briefing, priority alerts)
        4. Stores insights in Firestore
        """
        try:
            # Get user_id from metadata (populated from message payload)
            user_id = context.metadata.get("user_id") or context.user_id
            if not user_id:
                return AgentResult(success=False, error="No user_id provided")
            
            logger.info(f"Starting synthesis cycle for user {user_id}")
            
            # Step 1: Gather new information from agents
            gathered_data = await self._gather_information(user_id, context)
            
            # Step 2: Update social graph based on email interactions
            await self._update_social_graph(gathered_data, user_id)
            
            # Step 3: Synthesize information (now includes relationship context)
            insights = await self._synthesize_information(gathered_data, user_id)
            
            # Step 4: Store insights
            stored_insights = await self._store_insights(insights, user_id)
            
            # Update last sync time
            self.last_sync_times[user_id] = datetime.utcnow()
            
            logger.info(f"Synthesis cycle completed for user {user_id}")
            
            return AgentResult(
                success=True,
                data={
                    "insights_generated": len(stored_insights),
                    "insights": stored_insights,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Synthesis cycle failed: {e}")
            return AgentResult(
                success=False,
                error=str(e)
            )
    
    async def _gather_information(self, user_id: str, context: AgentContext = None) -> Dict[str, Any]:
        """
        Gather new information from various sources using message-based communication.
        This maintains proper decoupling between agents.
        
        Args:
            user_id: User identifier
            context: Agent context with orchestrator reference
            
        Returns:
            Dictionary containing gathered structured information (Working Memory)
        """
        working_memory = {
            "emails": [],
            "calendar_events": [],
            "tasks": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get last sync time for this user
        last_sync = self.last_sync_times.get(user_id, datetime.utcnow() - timedelta(hours=24))
        
        # Direct email processing using EmailAgent
        # TODO: In future, use orchestrator messaging when context includes orchestrator
        try:
            from app.agents.email_agent import EmailAgent
            email_agent = EmailAgent()
            
            # Process new emails since last sync
            processed_emails = await email_agent.process_new_emails(user_id, last_sync)
            working_memory["emails"] = processed_emails
            logger.info(f"Gathered {len(working_memory['emails'])} structured emails directly")
            
        except Exception as e:
            logger.error(f"Failed to get structured email data: {e}")
            working_memory["emails"] = []
        
        # TODO: Add calendar and task gathering via messaging when those agents are implemented
        
        return working_memory
    
    async def _update_social_graph(
        self,
        working_memory: Dict[str, Any],
        user_id: str
    ) -> None:
        """
        Update the user's social graph based on email interactions.
        Tracks relationships and interaction patterns.
        
        Args:
            working_memory: Contains processed emails with sender information
            user_id: User identifier
        """
        try:
            emails = working_memory.get("emails", [])
            if not emails:
                return
            
            logger.info(f"Updating social graph with {len(emails)} email interactions")
            
            # Group emails by sender
            interactions_by_sender = {}
            for email in emails:
                sender_email = self._extract_email_address(email.get("sender", ""))
                if not sender_email or "@" not in sender_email:
                    continue
                
                if sender_email not in interactions_by_sender:
                    interactions_by_sender[sender_email] = []
                
                interactions_by_sender[sender_email].append({
                    "date": email.get("date", datetime.utcnow().isoformat()),
                    "subject": email.get("subject", ""),
                    "intent": email.get("intent", "Unknown"),
                    "is_reply_needed": email.get("is_reply_needed", False),
                    "sentiment": email.get("sentiment", "neutral")
                })
            
            # Update contacts in Firestore
            for sender_email, interactions in interactions_by_sender.items():
                await self._update_contact(user_id, sender_email, interactions)
            
            logger.info(f"Updated {len(interactions_by_sender)} contacts in social graph")
            
        except Exception as e:
            logger.error(f"Failed to update social graph: {e}")
            # Don't fail the synthesis if social graph update fails
    
    def _extract_email_address(self, sender: str) -> str:
        """Extract email address from sender string like 'Name <email@domain.com>'"""
        import re
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1).lower()
        # If no angle brackets, assume the whole string is the email
        return sender.strip().lower() if "@" in sender else ""
    
    async def _update_contact(
        self,
        user_id: str,
        contact_email: str,
        interactions: List[Dict[str, Any]]
    ) -> None:
        """
        Update or create a contact record with latest interaction data.
        
        Args:
            user_id: User identifier
            contact_email: Contact's email address
            interactions: List of recent interactions with this contact
        """
        try:
            # Reference to contact document
            contact_ref = firebase_client.db.collection("users").document(user_id)\
                .collection("contacts").document(contact_email.replace(".", "_"))
            
            # Get existing contact or create new
            doc = contact_ref.get()
            
            if doc.exists:
                contact_data = doc.to_dict()
                # Append new interactions to history (keep last 50)
                interaction_history = contact_data.get("interaction_history", [])
                interaction_history.extend(interactions)
                interaction_history = interaction_history[-50:]  # Keep last 50 interactions
            else:
                # New contact
                contact_data = {
                    "email": contact_email,
                    "name": self._extract_name_from_email(contact_email),
                    "first_interaction": interactions[0]["date"] if interactions else None,
                    "interaction_history": interactions
                }
                interaction_history = interactions
            
            # Calculate relationship metrics
            latest_interaction = max(interactions, key=lambda x: x.get("date", "")) if interactions else None
            total_interactions = len(interaction_history)
            replies_needed = sum(1 for i in interaction_history if i.get("is_reply_needed", False))
            
            # Generate AI summary of relationship
            relationship_summary = await self._generate_relationship_summary(
                contact_email, interaction_history[-10:]  # Use last 10 interactions for summary
            )
            
            # Update contact data
            contact_data.update({
                "last_interaction_date": latest_interaction["date"] if latest_interaction else None,
                "total_interactions": total_interactions,
                "pending_replies": replies_needed,
                "relationship_summary": relationship_summary,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Save to Firestore
            contact_ref.set(contact_data, merge=True)
            
        except Exception as e:
            logger.error(f"Failed to update contact {contact_email}: {e}")
    
    def _extract_name_from_email(self, email: str) -> str:
        """Extract probable name from email address"""
        # Remove domain
        local_part = email.split("@")[0]
        # Replace common separators with spaces
        name = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
        # Capitalize words
        return " ".join(word.capitalize() for word in name.split())
    
    async def _generate_relationship_summary(
        self,
        contact_email: str,
        recent_interactions: List[Dict[str, Any]]
    ) -> str:
        """
        Generate an AI summary of the relationship based on interaction history.
        
        Args:
            contact_email: Contact's email
            recent_interactions: Recent interaction history
            
        Returns:
            Brief relationship summary
        """
        if not recent_interactions:
            return "No recent interactions"
        
        try:
            # Build a summary of interactions for the LLM
            interaction_summary = f"Contact: {contact_email}\n"
            interaction_summary += f"Number of recent interactions: {len(recent_interactions)}\n"
            interaction_summary += "Recent topics:\n"
            
            for interaction in recent_interactions[-5:]:  # Last 5 interactions
                interaction_summary += f"- {interaction.get('subject', 'No subject')}\n"
            
            prompt = f"""Based on these email interactions, provide a one-sentence summary of the relationship:
            {interaction_summary}
            
            Focus on: relationship type (colleague, client, friend), interaction frequency, and main topics discussed.
            Keep it under 50 words."""
            
            result = await llm_service.simple_completion(
                prompt=prompt,
                complexity=ModelComplexity.SIMPLE,
                max_tokens=100
            )
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate relationship summary: {e}")
            return "Relationship summary unavailable"
    
    async def _get_relationship_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get relationship context for synthesis.
        Identifies contacts needing attention.
        
        Args:
            user_id: User identifier
            
        Returns:
            Relationship context including stale relationships and pending replies
        """
        try:
            # Query contacts collection
            contacts_ref = firebase_client.db.collection("users").document(user_id).collection("contacts")
            
            # Get all contacts
            contacts = []
            for doc in contacts_ref.stream():
                contact = doc.to_dict()
                contact["id"] = doc.id
                contacts.append(contact)
            
            # Analyze relationship patterns
            now = datetime.utcnow()
            stale_threshold = timedelta(days=21)  # 3 weeks
            
            stale_relationships = []
            pending_replies = []
            
            for contact in contacts:
                last_interaction = contact.get("last_interaction_date")
                if last_interaction:
                    last_date = datetime.fromisoformat(last_interaction.replace("Z", "+00:00"))
                    if now - last_date > stale_threshold:
                        stale_relationships.append({
                            "email": contact["email"],
                            "name": contact.get("name", "Unknown"),
                            "days_since_contact": (now - last_date).days,
                            "summary": contact.get("relationship_summary", "")
                        })
                
                if contact.get("pending_replies", 0) > 0:
                    pending_replies.append({
                        "email": contact["email"],
                        "name": contact.get("name", "Unknown"),
                        "pending_count": contact["pending_replies"]
                    })
            
            return {
                "total_contacts": len(contacts),
                "stale_relationships": stale_relationships[:5],  # Top 5 stale
                "pending_replies": pending_replies[:5],  # Top 5 pending
                "active_contacts": len([c for c in contacts if c.get("total_interactions", 0) > 5])
            }
            
        except Exception as e:
            logger.error(f"Failed to get relationship context: {e}")
            return {
                "total_contacts": 0,
                "stale_relationships": [],
                "pending_replies": [],
                "active_contacts": 0
            }
    
    async def _perform_thematic_analysis(
        self,
        working_memory: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Stage 1: Perform thematic clustering of information.
        Groups related emails, events, and tasks into themes or projects.
        
        Args:
            working_memory: Structured data from various sources
            user_id: User identifier
            
        Returns:
            Dictionary mapping themes to related data points
        """
        if not working_memory["emails"]:
            return {"themes": {}, "uncategorized": []}
        
        # Build prompt for thematic analysis with JSON output using enriched data
        emails_data = []
        for idx, email in enumerate(working_memory["emails"][:50]):  # Process more emails
            emails_data.append({
                "index": idx,
                "subject": email['subject'],
                "summary": email.get('summary', 'N/A'),
                "intent": email.get('intent', 'Unknown'),
                "entities": email.get('entities', {}),
                "urgency_score": email.get('urgency_score', 1),
                "is_reply_needed": email.get('is_reply_needed', False)
            })
        
        prompt = f"""Analyze these emails and group them into coherent themes. PRIORITIZE work-related themes over marketing.
        Use the enriched metadata (intent, entities, urgency, is_work_related) to create meaningful groupings.
        
        Emails to analyze:
        {json.dumps(emails_data, indent=2)}
        
        Theme Creation Guidelines:
        1. WORK PROJECTS: Group by specific projects in entities.projects (GEN-IMPACT, research, deliverables)
        2. KEY PEOPLE: Group emails from important senders (high sender_importance)
        3. ACTION ITEMS: Group emails with commitments.tasks_for_me
        4. MEETINGS & EVENTS: Group meeting invitations and calendar items
        5. MARKETING: Group all urgency_score <= 2 promotional content together
        
        Prioritize creating themes like:
        - "Active Work Projects" (urgency >= 3, is_work_related=true)
        - "Team Communications" (from colleagues)
        - "Client Requests" (external high-importance senders)
        - "Pending Actions" (has tasks_for_me)
        - "Low Priority/Marketing" (urgency <= 2)
        
        Return a JSON object with this structure:
        {{
            "themes": {{
                "Active Work Projects": {{
                    "description": "Emails about ongoing work projects and deliverables",
                    "email_indices": [indices of work emails],
                    "average_urgency": 4.0,
                    "key_entities": {{"people": ["colleagues"], "projects": ["GEN-IMPACT"]}}
                }},
                "Marketing & Newsletters": {{
                    "description": "Promotional and marketing emails",
                    "email_indices": [indices of marketing emails],
                    "average_urgency": 1.0,
                    "key_entities": {{"companies": ["marketing companies"]}}
                }}
            }},
            "uncategorized_indices": []
        }}
        
        Create themes that separate work from noise. Return ONLY the JSON object."""
        
        try:
            result = await llm_service.simple_completion(
                prompt=prompt,
                complexity=ModelComplexity.MEDIUM,  # Use complexity enum
                max_tokens=1000
            )
            
            # Parse JSON result
            themes = self._parse_json_themes(result, working_memory)
            return themes
            
        except Exception as e:
            logger.error(f"Thematic analysis failed: {e}")
            return {"themes": {"General": working_memory["emails"]}, "uncategorized": []}
    
    async def _perform_priority_analysis(
        self,
        themes: Dict[str, Any],
        working_memory: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Stage 2: Analyze themes for priorities and social obligations.
        
        Args:
            themes: Thematically grouped information
            user_id: User identifier
            
        Returns:
            Structured analysis with priorities and social notes
        """
        # Prepare enriched themes data for analysis
        themes_summary = {}
        for theme_name, theme_data in themes.get("themes", {}).items():
            # Extract emails for this theme
            email_indices = theme_data.get("email_indices", []) if isinstance(theme_data, dict) else []
            theme_emails = []
            
            # Get emails from working memory using indices
            all_emails = working_memory.get("emails", [])
            
            for idx in email_indices[:10]:  # Limit per theme
                if idx < len(all_emails):
                    email = all_emails[idx]
                    theme_emails.append({
                        "summary": email.get('summary', ''),
                        "urgency_score": email.get('urgency_score', 1),
                        "commitments": email.get('commitments', {}),
                        "is_reply_needed": email.get('is_reply_needed', False),
                        "sender": email.get('sender', '')
                    })
            
            themes_summary[theme_name] = {
                "description": theme_data.get("description", "") if isinstance(theme_data, dict) else "",
                "average_urgency": theme_data.get("average_urgency", 0) if isinstance(theme_data, dict) else 0,
                "emails": theme_emails
            }
        
        prompt = f"""Analyze these themed groups to identify priorities. Focus on WORK-RELATED items and genuine commitments.
        The user has ADHD/autism traits and needs clear, actionable guidance.
        
        Themes with enriched data:
        {json.dumps(themes_summary, indent=2)}
        
        Priority Extraction Rules:
        1. URGENT: Only items with urgency_score >= 4 AND concrete commitments.tasks_for_me
        2. IMPORTANT: Work-related items (urgency_score >= 3) with specific actions needed
        3. SOCIAL: Emails with is_reply_needed=true from high/medium importance senders
        4. DEADLINES: Extract from commitments.deadlines field
        5. IGNORE: Marketing emails (urgency_score <= 2), newsletters, promotional content
        
        Return your analysis as a JSON object:
        {{
            "priorities": {{
                "urgent": ["Specific work task with deadline - include WHO requested it"],
                "important": ["Important work item - include project name if mentioned"],
                "deferred": ["Low priority but still work-related"]
            }},
            "social_notes": {{
                "replies_needed": ["Reply to [Name] about [specific topic]"],
                "relationship_nudges": ["Check in with [Name] - last contact [X days] ago"]
            }},
            "deadlines": ["YYYY-MM-DD: [Project/Task] - [Description]"],
            "focus_recommendation": "Most critical SINGLE action to take right now",
            "work_projects_mentioned": ["List any specific projects like GEN-IMPACT found in emails"]
        }}
        
        Be SPECIFIC - use actual names, projects, and deadlines from the data.
        Return ONLY the JSON object."""
        
        try:
            result = await llm_service.simple_completion(
                prompt=prompt,
                complexity=ModelComplexity.MEDIUM,  # Use complexity enum
                max_tokens=1000
            )
            
            # Parse JSON result
            try:
                analysis = json.loads(result.strip())
                # Ensure all expected keys exist
                if "priorities" not in analysis:
                    analysis["priorities"] = {"urgent": [], "important": [], "deferred": []}
                if "social_notes" not in analysis:
                    analysis["social_notes"] = []
                return analysis
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON, using fallback parsing")
                # Fallback to string parsing if JSON fails
                return {
                    "priorities": {
                        "urgent": self._extract_urgent_items(result),
                        "important": self._extract_important_items(result),
                        "deferred": self._extract_deferred_items(result)
                    },
                    "social_notes": self._extract_social_notes(result),
                    "raw_analysis": result
                }
            
        except Exception as e:
            logger.error(f"Priority analysis failed: {e}")
            return {
                "priorities": {"urgent": [], "important": [], "deferred": []},
                "social_notes": [],
                "raw_analysis": "Analysis failed"
            }
    
    async def _generate_advisor_insights(
        self,
        analysis: Dict[str, Any],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Stage 3: Generate final advisor insights using pre-analyzed data.
        Now includes user goals and relationship context for personalized advice.
        
        Args:
            analysis: Pre-analyzed structured data
            user_id: User identifier
            
        Returns:
            List of actionable insights
        """
        # Extract social notes properly based on new structure
        social_notes = analysis.get('social_notes', {})
        replies_needed = social_notes.get('replies_needed', []) if isinstance(social_notes, dict) else []
        nudges = social_notes.get('relationship_nudges', []) if isinstance(social_notes, dict) else []
        
        # Get user goals from GoalAgent
        user_goals = []
        try:
            from app.agents.goal_agent import GoalAgent
            goal_agent = GoalAgent()
            formatted_goals = await goal_agent.get_active_goals_for_synthesis(user_id)
            user_goals = [g["content"] for g in formatted_goals[:3]]  # Top 3 goals for context
        except Exception as e:
            logger.warning(f"Could not fetch user goals: {e}")
            user_goals = []
        
        # Get relationship context
        relationship_context = await self._get_relationship_context(user_id)
        
        # Build enhanced prompt with goals and relationship context
        stale_relationships = relationship_context.get('stale_relationships', [])
        pending_replies = relationship_context.get('pending_replies', [])
        
        prompt = f"""You are a wise, empathetic, and strategic advisor for a user with neurodivergent traits. 
Your goal is to reduce overwhelm and provide clear, actionable guidance. You have already performed a detailed analysis of their recent digital activity.

Here is your pre-computed analysis summary:

## Priority Assessment
- **Urgent Tasks:** {', '.join(analysis['priorities']['urgent'][:3]) if analysis['priorities']['urgent'] else 'None identified'}
- **Important Topics:** {', '.join(analysis['priorities']['important'][:3]) if analysis['priorities']['important'] else 'None identified'}
- **Deadlines:** {', '.join(analysis.get('deadlines', [])[:3]) if analysis.get('deadlines') else 'No deadlines'}

## Social Radar
- **People to Reply To:** {', '.join(replies_needed[:3]) if replies_needed else 'None'}
- **Relationship Nudges:** {', '.join(nudges[:2]) if nudges else 'None'}
- **Stale Relationships (>3 weeks):** {', '.join([f"{r['name']} ({r['days_since_contact']} days)" for r in stale_relationships[:2]]) if stale_relationships else 'None'}
- **Pending Replies:** {len(pending_replies)} people waiting for responses

## Goal Alignment
- **Active Goals:** {', '.join(user_goals) if user_goals else 'No goals set yet'}

Based *only* on the summary above, compose a briefing for your user. Structure your response into three distinct sections in markdown:

### 🎯 Top 3 Priorities for Now
List the three most critical actions. For each, provide a "why" (e.g., "to unblock the team") and a suggested "first step" to make it less daunting.

### 📡 On Your Radar
Briefly mention 2-3 important but not urgent topics. Frame these as things to "keep in mind" or "think about," not immediate pressures.

### 👥 Connections
Highlight key social interactions. Suggest a simple, concrete action (e.g., "Draft a quick reply to Jane acknowledging her email.").

Remember: Be warm but concise. Reduce cognitive load. Make the complex feel manageable."""
        
        try:
            result = await llm_service.simple_completion(
                prompt=prompt,
                complexity=ModelComplexity.COMPLEX,  # COMPLEX model for final synthesis
                max_tokens=1500
            )
            
            insights = []
            
            # Create daily briefing insight
            insights.append({
                "type": "daily_briefing",
                "title": "Your Intelligent Daily Brief",
                "content": result,
                "priority": "high" if analysis['priorities']['urgent'] else "normal",
                "metadata": {
                    "urgent_count": len(analysis['priorities']['urgent']),
                    "important_count": len(analysis['priorities']['important']),
                    "social_count": len(replies_needed) + len(nudges),
                    "active_goals": len(user_goals),
                    "stale_relationships": len(stale_relationships),
                    "pending_replies": len(pending_replies)
                },
                "created_at": datetime.utcnow().isoformat()
            })
            
            # Add priority alert if urgent items exist
            if analysis['priorities']['urgent']:
                insights.append({
                    "type": "priority_alert",
                    "title": "Urgent Items Requiring Attention",
                    "content": "\n".join(analysis['priorities']['urgent'][:5]),
                    "priority": "high",
                    "created_at": datetime.utcnow().isoformat()
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate advisor insights: {e}")
            return [{
                "type": "status_update",
                "title": "Synthesis Complete",
                "content": "Analysis completed but insight generation encountered an issue.",
                "priority": "low",
                "created_at": datetime.utcnow().isoformat()
            }]
    
    async def _synthesize_information(
        self,
        gathered_data: Dict[str, Any],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Orchestrate multi-stage synthesis of gathered information.
        Now performs thematic analysis, priority analysis, and insight generation.
        
        Args:
            gathered_data: Working memory with structured information
            user_id: User identifier
            
        Returns:
            List of generated insights
        """
        working_memory = gathered_data
        
        # Stage 1: Thematic Clustering
        logger.info("Stage 1: Performing thematic analysis...")
        themes = await self._perform_thematic_analysis(working_memory, user_id)
        
        # Stage 2: Priority & Social Analysis
        logger.info("Stage 2: Performing priority analysis...")
        analysis = await self._perform_priority_analysis(themes, working_memory, user_id)
        
        # Stage 3: Generate Advisor Insights
        logger.info("Stage 3: Generating advisor insights...")
        insights = await self._generate_advisor_insights(analysis, user_id)
        
        logger.info(f"Synthesis complete: Generated {len(insights)} insights")
        return insights
    
    def _parse_json_themes(self, llm_response: str, working_memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse JSON response from thematic analysis.
        
        Args:
            llm_response: JSON string from LLM
            working_memory: Original working memory for mapping indices
            
        Returns:
            Dictionary with themes containing actual email objects
        """
        try:
            # Try to parse as JSON
            result = json.loads(llm_response.strip())
            
            # Map indices back to actual email objects
            themes = {}
            emails = working_memory.get("emails", [])
            
            for theme_name, theme_data in result.get("themes", {}).items():
                theme_emails = []
                for idx in theme_data.get("email_indices", []):
                    if 0 <= idx < len(emails):
                        theme_emails.append(emails[idx])
                if theme_emails:
                    themes[theme_name] = theme_emails
            
            # Handle uncategorized
            uncategorized = []
            for idx in result.get("uncategorized_indices", []):
                if 0 <= idx < len(emails):
                    uncategorized.append(emails[idx])
            
            return {"themes": themes, "uncategorized": uncategorized}
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse JSON themes, using fallback: {e}")
            # Fallback to old string parsing method
            return self._parse_themes(llm_response, working_memory)
    
    def _parse_themes(self, llm_response: str, working_memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse LLM response to extract themes.
        
        Args:
            llm_response: Raw LLM response text
            working_memory: Original working memory for fallback
            
        Returns:
            Dictionary with themes and uncategorized items
        """
        themes = {}
        lines = llm_response.split('\n')
        current_theme = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a theme header (usually starts with caps or has a colon)
            if ':' in line and not line.startswith('-') and not line.startswith('*'):
                theme_name = line.split(':')[0].strip()
                current_theme = theme_name
                themes[current_theme] = []
            elif current_theme and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
                # This is an item under the current theme
                item_text = line.lstrip('-*• ').strip()
                # Try to match with actual emails
                for email in working_memory.get("emails", []):
                    if item_text.lower() in email.get('subject', '').lower() or \
                       item_text.lower() in email.get('summary', '').lower():
                        themes[current_theme].append(email)
                        break
        
        # If no themes were parsed, create a default
        if not themes:
            themes["General"] = working_memory.get("emails", [])
        
        return {"themes": themes, "uncategorized": []}
    
    def _extract_urgent_items(self, analysis_text: str) -> List[str]:
        """Extract urgent items from priority analysis."""
        urgent = []
        lines = analysis_text.split('\n')
        in_urgent_section = False
        
        for line in lines:
            line_lower = line.lower()
            if 'urgent' in line_lower and ':' in line:
                in_urgent_section = True
                continue
            elif in_urgent_section:
                if line.strip() and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
                    urgent.append(line.lstrip('-*• ').strip())
                elif ':' in line:  # Probably a new section
                    in_urgent_section = False
        
        return urgent[:5]  # Limit to 5 items
    
    def _extract_important_items(self, analysis_text: str) -> List[str]:
        """Extract important but not urgent items from priority analysis."""
        important = []
        lines = analysis_text.split('\n')
        in_important_section = False
        
        for line in lines:
            line_lower = line.lower()
            if 'important' in line_lower and 'urgent' not in line_lower and ':' in line:
                in_important_section = True
                continue
            elif in_important_section:
                if line.strip() and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
                    important.append(line.lstrip('-*• ').strip())
                elif ':' in line:  # Probably a new section
                    in_important_section = False
        
        return important[:5]
    
    def _extract_deferred_items(self, analysis_text: str) -> List[str]:
        """Extract items that can be deferred."""
        deferred = []
        lines = analysis_text.split('\n')
        in_deferred_section = False
        
        for line in lines:
            line_lower = line.lower()
            if ('defer' in line_lower or 'later' in line_lower or 'low' in line_lower) and ':' in line:
                in_deferred_section = True
                continue
            elif in_deferred_section:
                if line.strip() and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
                    deferred.append(line.lstrip('-*• ').strip())
                elif ':' in line:
                    in_deferred_section = False
        
        return deferred[:5]
    
    def _extract_social_notes(self, analysis_text: str) -> List[str]:
        """Extract social obligations and relationship notes."""
        social = []
        lines = analysis_text.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['social', 'reply', 'respond', 'meeting', 'follow up', 'thank', 'congratulate']):
                if line.strip() and not ':' in line:
                    social.append(line.strip())
        
        return social[:5]
    
    async def _store_insights(
        self,
        insights: List[Dict[str, Any]],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Store insights in Firestore.
        
        Args:
            insights: List of insights to store
            user_id: User identifier
            
        Returns:
            List of stored insights with their IDs
        """
        stored_insights = []
        
        for insight in insights:
            try:
                # Add user_id and status to insight
                insight["user_id"] = user_id
                insight["status"] = "new"
                insight["viewed_at"] = None
                
                # Store in Firestore
                doc_ref = firebase_client.db.collection("synthesis_insights").add(insight)
                
                # Add document ID to insight
                insight["id"] = doc_ref[1].id
                stored_insights.append(insight)
                
                logger.info(f"Stored insight {insight['type']} for user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to store insight: {e}")
        
        return stored_insights
    
    async def get_recent_insights(
        self,
        user_id: str,
        limit: int = 10,
        include_viewed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get recent insights for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of insights to return
            include_viewed: Whether to include viewed insights
            
        Returns:
            List of recent insights
        """
        try:
            # Simplified query to avoid index requirement
            # Get all insights for user and filter in memory
            query = firebase_client.db.collection("synthesis_insights") \
                .where("user_id", "==", user_id) \
                .limit(limit * 2)  # Get more to filter later
            
            docs = query.stream()
            
            insights = []
            for doc in docs:
                insight = doc.to_dict()
                insight["id"] = doc.id
                
                # Filter based on viewed status if needed
                if not include_viewed and insight.get("status") != "new":
                    continue
                    
                insights.append(insight)
            
            # Sort by created_at descending and limit
            insights.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return insights[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
            return []
    
    async def mark_insight_viewed(self, insight_id: str, user_id: str) -> bool:
        """
        Mark an insight as viewed.
        
        Args:
            insight_id: Insight document ID
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = firebase_client.db.collection("synthesis_insights").document(insight_id)
            doc_ref.update({
                "status": "viewed",
                "viewed_at": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Marked insight {insight_id} as viewed for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark insight as viewed: {e}")
            return False