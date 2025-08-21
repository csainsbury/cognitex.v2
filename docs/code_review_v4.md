<chatName="CognitexV3CodeReviewAndRefinement"/>
This is an excellent implementation of the v3 blueprint. You've successfully built out the core components of the "Wise Advisor" engine, including the multi-stage analysis in the `ProactiveSynthesisAgent`, the new `GoalAgent`, and the relationship mapping features. The code quality is high, and the detailed prompts show a deep understanding of the project's goals.

My review confirms your assessment that the behavior is still not optimal. The reason is a critical architectural issue where one component is overriding the intelligence of another. The good news is that the fix is concentrated in one place and will unlock the full potential of the excellent work you've done in the agents.

Here is my detailed analysis and implementation plan for refinement.

### High-Level Assessment: The Root Cause

The primary issue lies in `app/services/llm_service.py`. It violates the principle of being a stateless, generic service. Instead of simply passing agent requests to the LLM provider, it contains hardcoded logic that intercepts and rewrites the agent's instructions.

**The core problem:** The `_call_anthropic` method in `llm_service` tries to be "smart" about tool selection and summarization. This effectively ignores the sophisticated prompts you've crafted in `EmailAgent` and forces a simplistic, keyword-driven workflow. The `ProactiveSynthesisAgent` is then fed lower-quality, unstructured data, which limits the effectiveness of its own advanced reasoning pipeline.

By refactoring the `LLMService` to be a true, generic passthrough, we will allow the agents' carefully designed prompts to drive the AI's reasoning, which should resolve the sub-optimal behavior.

---

### 1. Critical Refactoring: `LLMService`

This is the highest-priority change. We must make the `LLMService` a stateless executor and move all domain-specific logic back into the agents.

**File to Modify:** `app/services/llm_service.py`

#### 1.1. Simplify `_call_anthropic` Method

*   **Location:** `_call_anthropic` method within the `LLMService` class.
*   **Problem:** The method contains large `if/elif` blocks with logic specific to email processing. This includes creating an "enhanced prompt" for tool selection and another block for generating summaries from tool results. This logic preempts and overrides the agent's own reasoning.
*   **Required Change:** Remove all the conditional blocks and custom prompt generation. The method should be simplified to a direct, generic wrapper for the Anthropic API client.

*   **Implementation Steps:**
    1.  Delete the entire `if tools and len(anthropic_messages) == 1:` block.
    2.  Delete the `elif len(messages) > 2:` block.
    3.  The method should now directly call the Anthropic client, passing through the messages and tools it receives from the calling agent.

*   **New Method Logic (Illustrative Snippet):**
    ```python
    # In LLMService class
    async def _call_anthropic(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generic wrapper for the Anthropic Claude API with tool support."""
        if not self.anthropic_client:
            logger.error("Anthropic client not initialized")
            return {"content": "Error: Anthropic client not available."}

        try:
            # 1. Determine model
            model_id = model or "claude-3-5-sonnet-20240620" # Or use a default from router

            # 2. Format messages (system prompt vs. user/assistant messages)
            system_prompt = None
            anthropic_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    # Ensure content is correctly formatted for tool use results
                    # (This part of the API contract needs careful handling)
                    anthropic_messages.append(msg)
            
            # 3. Make a single, generic API call
            response = self.anthropic_client.messages.create(
                model=model_id,
                max_tokens=2048, # Increase for complex tasks
                system=system_prompt,
                messages=anthropic_messages,
                tools=tools if tools else None,
                tool_choice={"type": "auto"} if tools else None,
            )

            # 4. Parse and return the response generically
            # This will require parsing logic to handle both text responses
            # and tool_use blocks from the Anthropic API response object.
            # The goal is to return a standardized dictionary that the agent can understand.
            # e.g., {"content": "...", "tool_calls": [...]}
            # ... parsing logic here ...

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            # ... error handling ...
    ```

*   **Architectural Impact:** This change restores the correct separation of concerns. The `LLMService` becomes a simple connector, and the `EmailAgent`'s prompts become the sole driver of its behavior, as intended by the blueprint.

---

### 2. Architectural Improvement: Structured Insights for the UI

The UI (`wise_advisor_dashboard.html`) currently has to parse a single markdown string to create its layout. This is brittle. We should make the API contract between the backend and frontend more robust.

**File to Modify:** `app/agents/proactive_synthesis_agent.py`

#### 2.1. Update `_generate_advisor_insights` to Produce JSON

*   **Location:** `_generate_advisor_insights` method.
*   **Problem:** The method's prompt asks the LLM for a markdown string, which the UI then has to parse. A change in the markdown formatting would break the UI.
*   **Required Change:** Modify the prompt to request a structured JSON object. The `daily_briefing` insight stored in Firestore will then contain this structured data, which can be sent directly to the frontend.

*   **New Prompt Logic (Illustrative Snippet):**
    ```python
    # In ProactiveSynthesisAgent._generate_advisor_insights()
    prompt = f"""
    You are a wise, empathetic, and strategic advisor...
    
    Based *only* on the summary above, compose a briefing for your user.
    Return your response as a single, valid JSON object with the following structure. Do not include any other text or markdown formatting.
    {{
      "top_priorities": [
        {{
          "title": "Most critical action #1",
          "why": "The reason this is important (e.g., 'to unblock the team').",
          "first_step": "A small, concrete first action to reduce overwhelm."
        }}
      ],
      "on_your_radar": [
        {{
          "title": "Important but not urgent topic",
          "context": "A brief note on why this is on the radar."
        }}
      ],
      "connections": [
        {{
          "person": "Name of the person",
          "suggestion": "A simple, concrete action (e.g., 'Draft a quick reply acknowledging her email')."
        }}
      ]
    }}
    """
    
    result_str = await llm_service.simple_completion(...)
    try:
        briefing_json = json.loads(result_str)
    except json.JSONDecodeError:
        # Handle cases where the LLM failed to produce valid JSON
        # You could try to parse the markdown as a fallback here.
        briefing_json = {"error": "Failed to generate structured briefing."}

    # Store the JSON object in the insight's 'content' field
    insights.append({
        "type": "daily_briefing",
        "title": "Your Intelligent Daily Brief",
        "content": briefing_json, # Store the dict, not a string
        # ... other fields
    })
    ```

*   **Impact:**
    *   **Backend:** The insight stored in Firestore is now structured.
    *   **API:** `insights_routes.py` will now return JSON in the `content` field for `daily_briefing` insights.
    *   **Frontend:** `wise_advisor_dashboard.html` can be updated to directly use this JSON, eliminating brittle string parsing and making the UI much more reliable.

---

### 3. Further Refinements & Suggestions

#### 3.1. Refine the `summarize_urgent_emails` Prompt
*   **File:** `app/agents/email_agent.py`
*   **Location:** `summarize_urgent_emails` method.
*   **Suggestion:** Now that `LLMService` is fixed, this method's prompt will be respected. It's a very good, detailed prompt. To make it even better, you could explicitly tell the LLM that its primary tool `search_emails` is powerful and encourage it to construct a smart query.
*   **Example Prompt Addition:**
    ```prompt
    # Add this to the beginning of the existing prompt
    "Your first step is to use the `search_emails` tool. Construct a single, effective query to find all potentially relevant emails based on the criteria below before analyzing them..."
    ```
    This guides the LLM to think about the search query itself, leading to better initial data filtering.

#### 3.2. Externalize Prompts
*   **Files:** All agent files (`email_agent.py`, `proactive_synthesis_agent.py`, etc.).
*   **Suggestion:** The prompts are becoming complex and are central to the application's logic. Storing them as large multi-line strings in Python code makes them hard to edit and manage.
*   **Recommendation:** Move prompts into separate files in the `app/prompts/` directory. You can load them as simple text files or use a templating engine like Jinja2 if they require dynamic data to be inserted. This cleans up the agent code and makes prompt engineering an independent, iterative task.

    *   **Example:**
        ```python
        # In an agent file
        from pathlib import Path

        prompt_template = Path("app/prompts/thematic_analysis.txt").read_text()
        prompt = prompt_template.format(emails_data=json.dumps(emails_data, indent=2))
        ```

By implementing these changes, particularly the critical refactoring of `LLMService`, you will align the codebase with the architectural vision of Blueprint v3 and should see a significant improvement in the quality and relevance of the insights generated by the system.