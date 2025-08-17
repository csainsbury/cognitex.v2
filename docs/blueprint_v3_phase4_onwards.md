<chatName="CognitexWiseAdvisorRefinementPlan"/>
This is an excellent and crucial architectural review. Your assessment is spot on: the system is drifting from its core purpose of being an "intelligent commentator" and is being subtly encouraged by the implementation details to perform lower-level, keyword-driven tasks. This is a common pitfall in building complex AI systems, where the scaffolding built around the model inadvertently constrains its reasoning capabilities.

The existing `blueprint_v2_phase4_onwards.md` provides a solid strategic direction. The issue lies not in the strategy itself, but in implementation details that subvert its intent. The multi-stage analysis pipeline is the correct approach, but it needs to be fed with richer data and be supported by a less restrictive AI service layer.

This new blueprint—let's call it **Blueprint v3**—will serve as a detailed implementation plan to correct this drift. It focuses on refining the existing Phase 4 implementation to enforce higher-level reasoning and then builds upon that corrected foundation for future phases.

---

## Blueprint v3: The "Wise Advisor" Engine - Implementation Plan

### Architectural Goal

Our primary goal is to force the system to perform a genuine synthesis of *all* new information, rather than seeking shortcuts. The `ProactiveSynthesisAgent` is the "Wise Advisor," and other agents are its "briefing staff." The staff's job is to prepare comprehensive, structured reports (not just answer simple questions), which the advisor then analyzes from multiple angles before delivering insights.

---

### Phase 4 (Refined): Achieving True AI-Driven Synthesis

This phase is a deep refactoring of the existing system to eliminate reasoning shortcuts and enrich the data pipeline.

#### 1. Decouple LLM Reasoning from Hardcoded Logic in `LLMService`

The most critical issue is that `llm_service.py` contains logic that pre-empts the AI's reasoning about tool use. This must be removed to allow the agents' prompts to drive the process.

*   **File to Modify:** `app/services/llm_service.py`
*   **Location:** `_call_anthropic` method.
*   **Problem:** The current implementation has `if/elif` blocks that check for keywords like "urgent" or "daily" in the prompt and then construct a hardcoded tool call. This is the primary source of the "keyword search" behavior.
*   **Required Change:**
    *   Remove the entire block of `if tools and len(anthropic_messages) == 1:` and its inner logic.
    *   The method should be simplified to *only* format the request for the Anthropic API and send it. It should pass the `tools` (tool schemas) directly to the API call.
    *   The responsibility of deciding *which* tool to call, and with *what arguments*, must be delegated entirely to the LLM, guided by the prompt from the calling agent (e.g., `EmailAgent`).

*   **New Logic for `_call_anthropic` (conceptual):**
    ```python
    # In LLMService._call_anthropic()
    
    # 1. Format messages and system prompt as before.
    # 2. Make a single API call to the Anthropic client, passing the messages, system prompt, and the tool schemas.
    #    client.messages.create(
    #        model=model,
    #        messages=anthropic_messages,
    #        system=system_prompt,
    #        tools=tools,
    #        ...
    #    )
    # 3. Process the response. If the response contains a tool_use block, parse it and return it.
    #    If it contains a final answer, return that.
    # 4. The method should be stateless and generic, containing no logic specific to emails or any other domain.
    ```
*   **Impact:** This change forces `EmailAgent`'s prompts to be the sole driver of the reasoning process. The quality of the prompt in `summarize_urgent_emails` will now directly determine the quality of the tool use.

#### 2. Enhance `EmailAgent` for Richer Structured Data Extraction

The `EmailAgent`'s role as a "briefer" must be solidified. Its `process_new_emails` method should produce a more detailed and consistent structured output for *every* email, which becomes the foundation for all subsequent analysis.

*   **File to Modify:** `app/agents/email_agent.py`
*   **Location:** `_process_email_batch` method.
*   **Problem:** The current extraction is good but can be made more comprehensive to better support the synthesis agent.
*   **Required Change:**
    *   Update the prompt in `_process_email_batch` to extract more nuanced information.
    *   The JSON output schema should be expanded.

*   **New Prompt Structure for `_process_email_batch`:**
    ```prompt
    Analyze the following email batch. For each email, extract a structured JSON object.

    Emails:
    {json.dumps(email_batch, indent=2)}

    For each email, provide a JSON object with this EXACT structure:
    {
        "id": "email_id",
        "summary": "A concise, one-sentence summary of the email's core message.",
        "intent": "Classify the sender's primary intent (e.g., 'Question', 'Request for Action', 'Informational', 'Social', 'Advertisement').",
        "entities": {
            "people": ["Name1", "Name2"],
            "companies": ["Company1"],
            "projects": ["Project Alpha"]
        },
        "commitments": {
            "tasks_for_me": ["Action item I need to do."],
            "tasks_for_others": ["Action item someone else was asked to do."],
            "deadlines": ["YYYY-MM-DD: Description of deadline."]
        },
        "sentiment": "positive | negative | neutral",
        "is_reply_needed": true | false,
        "urgency_score": "An integer from 1 (low) to 5 (high) based on content, not just keywords."
    }
    
    Return ONLY a valid JSON array of these objects.
    ```
*   **Impact:** This provides the `ProactiveSynthesisAgent` with a much richer "working memory," enabling more sophisticated analysis of intent, commitments, and urgency.

#### 3. Refine `ProactiveSynthesisAgent` Multi-Stage Analysis

With richer input data, the prompts for each stage of synthesis can be more powerful.

*   **File to Modify:** `app/agents/proactive_synthesis_agent.py`
*   **Location:** `_perform_thematic_analysis`, `_perform_priority_analysis`, `_generate_advisor_insights` methods.
*   **Required Changes:**

    *   **In `_perform_thematic_analysis`:** Update the prompt to use the new `intent` and `entities` fields for better clustering.
        ```prompt
        // Prompt for _perform_thematic_analysis
        ...
        Emails to analyze:
        // Pass a summary including subject, summary, intent, and entities.
        ...
        Group these emails into themes based on project, topic, and intent.
        ...
        ```

    *   **In `_perform_priority_analysis`:** Update the prompt to leverage the `urgency_score` and `commitments` from the structured data.
        ```prompt
        // Prompt for _perform_priority_analysis
        ...
        Themes to analyze:
        // Pass a summary of each theme, highlighting average urgency_score, key commitments, and deadlines.
        ...
        Based on this data, identify urgent tasks (from commitments), important topics (from high-urgency themes), and social obligations (from 'is_reply_needed' and social intents).
        ...
        ```

    *   **In `_generate_advisor_insights` (rename from `_build_final_insight_prompt` logic):** This is the final step. The prompt should be explicitly framed around the "Wise Advisor" persona.
        ```prompt
        You are a wise, empathetic, and strategic advisor for a user with neurodivergent traits. Your goal is to reduce overwhelm and provide clear, actionable guidance. You have already performed a detailed analysis of their recent digital activity.

        Here is your pre-computed analysis summary:

        ## Key Themes & Topics
        {themes_summary}

        ## Priority Assessment
        - **Urgent Tasks:** {analysis.priorities.urgent}
        - **Important Topics:** {analysis.priorities.important}

        ## Social Radar
        - **People to Reply To:** {analysis.social_notes.replies_needed}
        - **Relationship Nudges:** {analysis.social_notes.nudges}

        ## Goal Alignment
        - **Active Goals:** {user_goals}
        - **Tasks that advance goals:** {goal_aligned_tasks}

        Based *only* on the summary above, compose a briefing for your user. Structure your response into three distinct sections in markdown:

        ### 🎯 Top 3 Priorities for Now
        List the three most critical actions. For each, provide a "why" (e.g., "to unblock the team") and a suggested "first step" to make it less daunting.

        ### 📡 On Your Radar
        Briefly mention 2-3 important but not urgent topics. Frame these as things to "keep in mind" or "think about," not immediate pressures.

        ### 👥 Connections
        Highlight key social interactions. Suggest a simple, concrete action (e.g., "Draft a quick reply to Jane acknowledging her email.").
        ```

*   **Impact:** These refined prompts, combined with the richer input data, guide the LLM through a robust analytical process, making a simple keyword-based summary an insufficient answer.

---

### Phase 5 (New): User Goals & Relationship Mapping

This phase introduces long-term context, which is essential for the advisor to provide truly personalized and strategic advice. The plan from Blueprint v2 is excellent and we will adopt it with minor clarifications.

#### 1. Goal Management Agent & API

*   **New File:** `app/agents/goal_agent.py`
    *   **Purpose:** A simple agent to manage a user's goals via CRUD operations.
*   **New File:** `app/api/goal_routes.py`
    *   **Purpose:** User-facing API for goal management.
    *   **Endpoints:** `POST /api/v1/goals`, `GET /api/v1/goals`, `PUT /api/v1/goals/{id}`, `DELETE /api/v1/goals/{id}`.
*   **Data Storage:** Create a new `user_goals` collection in Firestore. Schema: `{ "user_id", "content", "type": "short|medium|long_term", "status": "active|completed|archived", "created_at" }`.
*   **Integration:**
    *   `ProactiveSynthesisAgent` will fetch active goals from Firestore in its `_run_synthesis_cycle`.
    *   The list of goals will be passed to `_generate_advisor_insights` and included in the prompt as shown above.

#### 2. Relationship Mapping

*   **New Data Structure:** A `contacts` sub-collection under each user in Firestore (`users/{user_id}/contacts/{contact_email}`).
    *   **Schema:** `{ "name", "email", "last_interaction_date", "interaction_history": [...], "notes": "AI-generated summary of relationship" }`.
*   **File to Modify:** `app/agents/proactive_synthesis_agent.py`
    *   **New Method:** `_update_social_graph(working_memory, user_id)`
    *   **Logic:**
        1.  Called during the synthesis cycle.
        2.  Iterates through the structured emails from `working_memory`.
        3.  For each correspondent, it updates their document in the `contacts` collection.
    *   **Integration:** `_perform_priority_analysis` will query this collection to identify relationship opportunities (e.g., "You haven't spoken to Contact X in 3 weeks").

---

### Phase 6 (New): The "Wise Advisor" UI & Feedback Loop

The user interface must evolve to present these higher-level insights effectively.

*   **File to Modify:** `app/ui/templates/wise_advisor_dashboard.html`
    *   **UI Redesign:** This dashboard should replace `insights_dashboard.html` as the primary view.
    *   It will not be a feed. It will be a static layout with dedicated sections that are refreshed after each synthesis cycle:
        *   **Top Priorities:** A prominent card displaying the "Top 3 Priorities" from the latest insight.
        *   **On Your Radar:** A section for the less urgent topics.
        *   **Connections:** A section for the social nudges.
*   **Feedback Mechanism:**
    *   **UI:** Add "👍 Useful / 👎 Not Useful" buttons to each insight section.
    *   **API:** New endpoint `POST /api/v1/insights/{id}/feedback` in `insights_routes.py`.
    *   **Storage:** Store feedback in Firestore, linked to the insight. This data is crucial for future fine-tuning of the advisor's prompts.

By implementing this refined blueprint, we directly address the architectural drift and build a more robust foundation for the intelligent, proactive "wise advisor" that is the core vision of Cognitex.