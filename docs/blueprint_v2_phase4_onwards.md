<chatName="CognitexWiseAdvisorBlueprint"/>

Thank you for the detailed context and feedback. It's a common and critical challenge in building sophisticated AI systems: preventing the model from taking simplistic shortcuts and ensuring it performs the desired high-level reasoning. Your "wise advisor" concept is the perfect articulation of the project's core goal.

My analysis confirms your assessment. The current implementation, while functional, encourages the `EmailAgent` to perform low-level data filtering (e.g., searching for "urgent" emails) rather than providing rich, structured data for a higher-level synthesis agent to analyze.

To steer the project back towards the vision of an intelligent commentator, we will revise the blueprint from Phase 4 onwards. The new strategy focuses on separating data collection and structuring from the final synthesis, creating a richer "working memory" for the synthesis agent, and explicitly modeling user goals and relationships.

---

## Revised Architectural Strategy: The "Wise Advisor" Engine

The core shift is to move from a reactive, query-based system to a proactive, multi-stage analysis pipeline.

1.  **Decouple Ingestion from Synthesis:** Data-source agents (like `EmailAgent`) will be responsible for fetching *and pre-processing* new information into a structured format. They will no longer be asked for "summaries of urgent things." Instead, they will provide a structured feed of *all* new information.
2.  **Establish a "Working Memory":** The `ProactiveSynthesisAgent` will collate this structured data from all sources into a temporary, coherent context for each synthesis cycle. This becomes the "information on the desk" for the wise advisor.
3.  **Multi-Stage Analysis:** The synthesis process will be broken down into distinct analytical steps: thematic clustering, priority assessment, social network analysis, and goal alignment. This forces a deeper level of reasoning than a single, monolithic prompt.
4.  **Explicit Goal & Relationship Modeling:** We will introduce dedicated agents and data stores for managing user goals and tracking professional relationships, making these first-class citizens in the synthesis process.
5.  **Focus on Actionable Advice:** The final output will be tailored advice and observations, not just summaries. The UI will reflect this by presenting insights in categories like "Priorities," "Social Radar," and "Goal Progress."

---

## Revised Blueprint: Phase 4 Onwards

### Phase 4 (Revised): The Advanced Synthesis Engine

This phase refactors the core synthesis process to enable higher-level reasoning.

#### 1. Refactor `EmailAgent` for Structured Data Extraction

The `EmailAgent`'s role will shift from on-demand summarization to periodic, structured processing of new emails.

*   **File to Modify:** `app/agents/email_agent.py`
    *   **Change:** Modify the `process` method to handle a new task for structured data extraction.
    *   **Logic:** The `process` method will route tasks. The existing tasks (`summarize_urgent_emails`, etc.) will remain for direct API calls, but we will add a new internal-facing task.
    *   **New Method Signature:**
        ```python
        # In class EmailAgent(BaseAgent):
        async def process_new_emails(self, user_id: str, since: datetime) -> List[Dict[str, Any]]:
            """
            Fetches new emails since a given timestamp, processes each one to extract
            structured data, and returns a list of structured email objects.
            """
            # 1. Use gmail_tools.search_emails to find new emails.
            # 2. For each email, use gmail_tools.get_email_details.
            # 3. For each full email, make a SIMPLE llm_service call to:
            #    - Generate a one-sentence summary.
            #    - Extract key entities (people, companies, projects).
            #    - Identify explicit tasks, questions, or deadlines.
            #    - Determine sentiment (positive, negative, neutral).
            # 4. Return a list of structured dictionaries, e.g.:
            #    { "id": "...", "subject": "...", "sender": "...", "summary": "...", "tasks": [...], "sentiment": "..." }
        ```
    *   **Change:** Update the `process` method to call `process_new_emails` when it receives a corresponding task from the `ProactiveSynthesisAgent`.

        ```python
        # In EmailAgent.process()
        elif task == "process_new_emails":
            since_str = context.metadata.get("since")
            since_dt = datetime.fromisoformat(since_str) if since_str else datetime.utcnow() - timedelta(hours=24)
            result = await self.process_new_emails(user_id, since_dt)
            return AgentResult(success=True, data={"processed_emails": result})
        ```

#### 2. Refactor `ProactiveSynthesisAgent` to Orchestrate Deeper Analysis

This agent becomes the "Chief of Staff," orchestrating the multi-stage analysis.

*   **File to Modify:** `app/agents/proactive_synthesis_agent.py`
    *   **Change:** Overhaul the `_run_synthesis_cycle` and related methods.
    *   **Modify `_gather_information`:**
        *   This method will now send a `process_new_emails` command to the `EmailAgent` instead of a vague summarization request.
        *   It will collect the structured data from the `EmailAgent` (and future agents for calendar, tasks).
        *   The collected data forms the "Working Memory" for this cycle.

    *   **Modify `_synthesize_information`:**
        *   This method will now perform a multi-step analysis using the "Working Memory."
        *   **Reasoning:** Instead of one large prompt, we break it down. This improves reliability and allows for more complex reasoning.
        *   **New Logic:**
            ```python
            # In ProactiveSynthesisAgent._synthesize_information()
            
            # 1. Thematic Clustering (using a MEDIUM complexity LLM call)
            #    - Prompt: "Given these data points (emails, events), group them into themes or projects."
            #    - Result: A dictionary mapping themes to related data points.
            working_memory = gathered_data 
            themes = await self._perform_thematic_analysis(working_memory, user_id)

            # 2. Priority & Social Analysis (another MEDIUM LLM call)
            #    - Prompt: "Analyze these themes. Identify urgent tasks, important but not urgent items,
            #      and any social obligations or opportunities (e.g., need to reply, someone is waiting)."
            #    - Result: A structured object with priorities and social notes.
            analysis = await self._perform_priority_analysis(themes, user_id)
            
            # 3. Final Insight Generation (using a COMPLEX model)
            #    - This step now uses the pre-analyzed data to generate the final "wise advisor" text.
            #    - The prompt will be much more targeted.
            insights = await self._generate_advisor_insights(analysis, user_id)
            
            return insights
            ```

    *   **Modify `_build_synthesis_prompt` (to be renamed `_build_final_insight_prompt`):**
        *   This prompt will no longer receive raw data. It will receive the structured output from the analysis steps.
        *   **New Prompt Structure:**
            ```prompt
            You are a wise advisor and chief of staff for a user with neurodivergent traits.
            Your goal is to provide clear, actionable, and reassuring guidance.
            
            Here is my analysis of their current situation:
            
            PRIORITY TASKS:
            - {analysis.priorities.urgent}
            
            IMPORTANT TOPICS TO CONSIDER:
            - {analysis.priorities.important}
            
            SOCIAL RADAR:
            - {analysis.social_notes}
            
            Based *only* on the analysis above, provide a concise briefing for the user. Structure your response into three sections:
            1.  **Top 3 Priorities:** What they should focus on now.
            2.  **On Your Radar:** Important things to keep in mind.
            3.  **Connections:** People-related actions or observations.
            
            Be direct, empathetic, and focus on reducing overwhelm.
            ```

### Phase 5 (New): User Goals & Relationship Mapping

This phase introduces the long-term context needed for the "wise advisor" to be truly effective.

#### 1. Goal Management Agent & API

*   **New File:** `app/agents/goal_agent.py`
    *   **Purpose:** A simple agent to manage a user's goals. It will primarily be a data manager.
    *   **Class `GoalAgent(BaseAgent)`:** Will have methods to handle CRUD operations for goals.
*   **New File:** `app/api/goal_routes.py`
    *   **Purpose:** To provide a user-facing API for managing their goals.
    *   **Endpoints:**
        *   `POST /api/goals`: Create a new goal (e.g., `{ "content": "Publish research paper", "type": "long_term", "status": "active" }`).
        *   `GET /api/goals`: List all goals.
        *   `PUT /api/goals/{goal_id}`: Update a goal.
        *   `DELETE /api/goals/{goal_id}`: Delete a goal.
    *   **Data Storage:** Goals will be stored in a new `user_goals` collection in Firestore.
*   **Integration with Synthesis:**
    *   The `ProactiveSynthesisAgent` will fetch the user's active goals from Firestore during its cycle.
    *   The goals will be passed to the `_generate_advisor_insights` step. The prompt will be updated to include: "Consider how these priorities align with the user's long-term goals: {user_goals}."

#### 2. Relationship Mapping

*   **New Data Structure:** Define a `contacts` collection in Firestore for each user. A contact document will store: `name`, `email`, `last_interaction_date`, `interaction_frequency`, `latest_topics`, `overall_sentiment`.
*   **File to Modify:** `app/agents/proactive_synthesis_agent.py`
    *   **New Method:** `_update_social_graph(working_memory, user_id)`
    *   **Logic:**
        1.  This method will be called during the synthesis cycle.
        2.  It will iterate through the structured communication data (emails).
        3.  For each person involved, it will update their corresponding document in the `contacts` collection in Firestore.
        4.  It can use a `SIMPLE` LLM call to summarize the interaction topic if needed.
    *   **Integration:** The `_perform_priority_analysis` step will now also query the `contacts` collection to identify relationship opportunities (e.g., "Contact X hasn't been spoken to in 3 weeks").

### Phase 6 (New): The "Wise Advisor" UI & Feedback Loop

This phase focuses on presenting the new, higher-quality insights to the user effectively.

*   **File to Modify:** `app/ui/templates/insights_dashboard.html` and its corresponding JavaScript.
    *   **UI Redesign:**
        *   Instead of a single chronological feed, redesign the dashboard into thematic sections:
            *   A prominent "Top 3 Priorities for Today" card.
            *   A "Social Radar" section for relationship-based insights.
            *   A "Goal Progress" section that highlights tasks aligned with goals.
    *   **Insight Types:** The `synthesis_insights` documents in Firestore will now have more specific types, such as `priority_briefing`, `social_nudge`, `goal_alignment_update`. The UI will render them differently based on type.

*   **Implement a Feedback Mechanism:**
    *   **UI Change:** Add simple feedback buttons (e.g., "👍 Useful", "👎 Not Useful") to each insight card on the dashboard.
    *   **New API Endpoint:** Create `POST /api/insights/{insight_id}/feedback` in `app/api/insights_routes.py`.
    *   **Logic:**
        1.  The endpoint will store the feedback in Firestore, linked to the insight.
        2.  **Future Enhancement:** This feedback data can be periodically summarized and included in the `ProactiveSynthesisAgent`'s system prompt to fine-tune its output over time (e.g., "The user finds social nudges highly valuable but dislikes vague summaries.").

This revised plan creates a clear path to evolving Cognitex from a data summarizer into the "wise advisor" you envision. It introduces the necessary architectural changes to support deep, multi-faceted reasoning while building upon the existing codebase.