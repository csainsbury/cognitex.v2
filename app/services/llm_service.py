"""
LLM service for AI operations with tool calling support
"""
import logging
from typing import List, Dict, Any, Optional, Callable
import json
import inspect
from enum import Enum
from datetime import datetime, timedelta

from app.config import settings
from app.services.ai_model_router import ai_model_router, ModelComplexity

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    LOCAL = "local"

class LLMService:
    """
    Service for interacting with LLMs with tool calling support.
    Supports multiple providers and model routing.
    """
    
    def __init__(self):
        """Initialize LLM service"""
        self.anthropic_client = None
        self.openai_client = None
        
        # Initialize clients based on available API keys
        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic library not installed")
        
        if settings.OPENAI_API_KEY:
            try:
                import openai
                openai.api_key = settings.OPENAI_API_KEY
                self.openai_client = openai
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
    
    def function_to_tool_schema(self, func: Callable) -> Dict[str, Any]:
        """
        Convert a Python function to a tool schema for LLM.
        
        Args:
            func: Python function with docstring and type hints
            
        Returns:
            Tool schema dictionary
        """
        # Get function signature
        sig = inspect.signature(func)
        
        # Parse docstring
        docstring = inspect.getdoc(func) or ""
        lines = docstring.split('\n')
        description = lines[0] if lines else func.__name__
        
        # Build parameters schema
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            # Skip 'self' and special parameters
            if param_name in ['self', 'cls']:
                continue
            
            # Get type hint
            param_type = param.annotation
            
            # Convert Python type to JSON schema type
            json_type = "string"  # default
            if param_type == int:
                json_type = "integer"
            elif param_type == float:
                json_type = "number"
            elif param_type == bool:
                json_type = "boolean"
            elif param_type == list or str(param_type).startswith('List'):
                json_type = "array"
            elif param_type == dict or str(param_type).startswith('Dict'):
                json_type = "object"
            
            # Add to schema
            parameters["properties"][param_name] = {
                "type": json_type,
                "description": f"Parameter {param_name}"
            }
            
            # Check if required
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)
        
        return {
            "name": func.__name__,
            "description": description,
            "parameters": parameters
        }
    
    async def execute_with_tools(
        self,
        prompt: str,
        tools: List[Callable],
        model: Optional[str] = None,
        complexity: Optional[ModelComplexity] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute LLM reasoning with tool calling support.
        
        Args:
            prompt: The user prompt/task
            tools: List of callable functions the LLM can use
            model: Model to use (if None, uses default)
            max_iterations: Maximum tool calling iterations
            **kwargs: Additional arguments for tool execution
            
        Returns:
            Dictionary with final response and tool call history
        """
        # Convert tools to schemas
        tool_schemas = [self.function_to_tool_schema(tool) for tool in tools]
        tool_map = {tool.__name__: tool for tool in tools}
        
        # Select model based on complexity if not specified
        if not model and complexity:
            model_config = ai_model_router.select_model(complexity)
            model = model_config.model_id
            logger.info(f"Selected model {model_config.name} for complexity {complexity}")
        
        # Build initial messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant with access to tools. Use them to complete the user's request."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        # Tool calling loop
        iterations = 0
        tool_history = []
        
        while iterations < max_iterations:
            iterations += 1
            
            # Call LLM with tools
            response = await self._call_llm_with_tools(
                messages=messages,
                tools=tool_schemas,
                model=model
            )
            
            # Check if LLM wants to use a tool
            tool_calls = response.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("arguments", {})
                    
                    logger.info(f"LLM calling tool: {tool_name} with args: {tool_args}")
                    
                    # Execute tool
                    if tool_name in tool_map:
                        try:
                            # Add kwargs to tool arguments
                            tool_args.update(kwargs)
                            result = tool_map[tool_name](**tool_args)
                            
                            tool_history.append({
                                "tool": tool_name,
                                "arguments": tool_args,
                                "result": result
                            })
                            
                            # Add tool result to conversation
                            tool_result_json = json.dumps(result, default=str)
                            logger.info(f"Tool {tool_name} returned {len(result)} items" if isinstance(result, list) else f"Tool result type: {type(result)}")
                            messages.append({
                                "role": "assistant",
                                "content": f"Tool {tool_name} returned: {tool_result_json}"
                            })
                            
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {e}")
                            messages.append({
                                "role": "assistant",
                                "content": f"Error executing {tool_name}: {str(e)}"
                            })
                    else:
                        logger.error(f"Unknown tool: {tool_name}")
            else:
                # LLM provided final answer
                return {
                    "response": response.get("content", ""),
                    "final_response": response.get("final_response", response.get("content", "")),
                    "tool_history": tool_history,
                    "tool_calls": response.get("tool_calls", len(tool_history)),
                    "iterations": iterations
                }
        
        return {
            "response": "Max iterations reached without final answer",
            "tool_history": tool_history,
            "iterations": iterations
        }
    
    async def _call_llm_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call LLM with tool definitions.
        This is a simplified version - you'd implement actual API calls here.
        
        Args:
            messages: Conversation history
            tools: Tool schemas
            model: Model to use
            
        Returns:
            LLM response with potential tool calls
        """
        # For now, return a mock response
        # In production, this would call Anthropic/OpenAI APIs
        
        if self.anthropic_client and settings.ANTHROPIC_API_KEY:
            # Use Anthropic Claude
            return await self._call_anthropic(messages, tools, model)
        elif self.openai_client and settings.OPENAI_API_KEY:
            # Use OpenAI
            return await self._call_openai(messages, tools, model)
        else:
            # Fallback to mock response for testing
            return self._mock_llm_response(messages, tools)
    
    async def _call_anthropic(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        if not self.anthropic_client:
            logger.error("Anthropic client not initialized")
            return self._mock_llm_response(messages, tools)
        
        try:
            # Use default model if not specified
            if not model:
                model = "claude-3-haiku-20240307"  # Default to Haiku for cost efficiency
            
            # Convert messages to Anthropic format
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] == "user":
                    anthropic_messages.append({
                        "role": "user",
                        "content": msg["content"]
                    })
                elif msg["role"] == "assistant":
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
            
            # If we have tools and this is the first call, let Claude decide what to do
            if tools and len(anthropic_messages) == 1:
                # Build tool descriptions for Claude
                tool_descriptions = []
                for tool in tools:
                    desc = f"Tool: {tool['name']}\n"
                    desc += f"Description: {tool['description']}\n"
                    if 'parameters' in tool and 'properties' in tool['parameters']:
                        desc += "Parameters:\n"
                        for param, details in tool['parameters']['properties'].items():
                            desc += f"  - {param}: {details.get('description', 'No description')}\n"
                    tool_descriptions.append(desc)
                
                # Create an enhanced prompt that includes tool information
                enhanced_prompt = f"""
{anthropic_messages[0]['content']}

You have access to the following tools:

{''.join(tool_descriptions)}

Based on the user's request above, decide which tool to use and with what parameters.
Respond with a JSON object in this format:
{{
    "tool_name": "<tool_name>",
    "arguments": {{
        // tool arguments
    }}
}}

Think carefully about what would best serve the user's needs. Consider:
- The time range that would capture relevant information
- The number of results needed for comprehensive analysis
- Any specific search criteria that would help find the most relevant items
"""
                
                # Call Claude to decide on tool use
                response = self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system_message or "You are an intelligent assistant that can use tools to help users.",
                    messages=[{"role": "user", "content": enhanced_prompt}]
                )
                
                # Parse Claude's response to get tool call
                try:
                    response_text = response.content[0].text
                    # Try to extract JSON from response
                    import re
                    json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                    if json_match:
                        tool_decision = json.loads(json_match.group())
                        return {
                            "tool_calls": [{
                                "name": tool_decision.get("tool_name", "search_emails"),
                                "arguments": tool_decision.get("arguments", {})
                            }]
                        }
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(f"Could not parse tool decision from Claude: {e}")
                    # Fallback: use a sensible default
                    return {
                        "tool_calls": [{
                            "name": "search_emails",
                            "arguments": {
                                "query": "newer_than:7d",
                                "max_results": 100
                            }
                        }]
                    }
            
            # We have tool results - generate summary
            elif len(messages) > 2:  # We have tool results
                # Build a proper conversation for Claude with the actual email data
                claude_messages = []
                
                # Add the original request
                claude_messages.append({
                    "role": "user",
                    "content": anthropic_messages[0]["content"] if anthropic_messages else "Summarize urgent emails"
                })
                
                # Extract and parse tool results
                email_data = None
                for msg in messages[2:]:  # Skip system and initial user message
                    if msg["role"] == "assistant" and "Tool" in msg["content"]:
                        # Parse the JSON from tool result
                        try:
                            if "returned:" in msg["content"]:
                                json_str = msg["content"].split("returned:", 1)[1].strip()
                                email_data = json.loads(json_str)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse tool result: {msg['content'][:200]}")
                
                # If we have email data, create proper summary
                if email_data and isinstance(email_data, list) and len(email_data) > 0:
                    email_summary = f"Here are ALL {len(email_data)} emails found:\n\n"
                    # Pass ALL emails to Claude for intelligent assessment
                    for i, email in enumerate(email_data, 1):
                        email_summary += f"Email {i}:\n"
                        email_summary += f"From: {email.get('sender', email.get('from', 'Unknown'))}\n"
                        email_summary += f"Subject: {email.get('subject', 'No subject')}\n"
                        email_summary += f"Date: {email.get('date', 'Unknown')}\n"
                        if email.get('snippet'):
                            email_summary += f"Preview: {email.get('snippet')[:150]}\n"
                        email_summary += "\n"
                    
                    claude_messages.append({
                        "role": "assistant",
                        "content": email_summary
                    })
                else:
                    # No emails found
                    claude_messages.append({
                        "role": "assistant",
                        "content": "No emails were found matching the search criteria."
                    })
                
                # Ask Claude to summarize based on the tool results
                claude_messages.append({
                    "role": "user",
                    "content": "Based on the emails found above, please provide a concise summary highlighting the most important/urgent items and any required actions."
                })
                
                # Call Claude with the full context
                response = self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system="You are a helpful AI assistant analyzing emails. Provide concise, actionable summaries.",
                    messages=claude_messages
                )
                
                return {
                    "content": response.content[0].text,
                    "final_response": response.content[0].text
                }
            
            # Default response if no special handling
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_message or "You are a helpful AI assistant.",
                messages=anthropic_messages if anthropic_messages else [{"role": "user", "content": "Hello"}]
            )
            
            return {
                "content": response.content[0].text
            }
            
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return self._mock_llm_response(messages, tools)
    
    async def _call_openai(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call OpenAI API"""
        # Implementation would go here
        # For now, return mock
        return self._mock_llm_response(messages, tools)
    
    def _mock_llm_response(
        self,
        messages: List[Dict],
        tools: List[Dict]
    ) -> Dict[str, Any]:
        """
        Mock LLM response for testing without API keys.
        """
        user_message = messages[-1]["content"] if messages else ""
        
        # Check if this is asking for email processing
        if "email" in user_message.lower():
            # First, use appropriate tool based on request
            if not any("Tool" in m.get("content", "") for m in messages):
                # Determine which tool to use based on the actual request
                if "process" in user_message.lower() or "new" in user_message.lower():
                    return {
                        "tool_calls": [{
                            "name": "get_emails_since",
                            "arguments": {
                                "since": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
                                "max_results": 50
                            }
                        }]
                    }
                else:
                    # Generic search
                    return {
                        "tool_calls": [{
                            "name": "search_emails",
                            "arguments": {
                                "query": "is:unread",
                                "max_results": 10
                            }
                        }]
                    }
            else:
                # We've already searched, provide summary
                return {
                    "content": "Based on the email analysis, I've identified several items that require your attention. The analysis includes priority levels, required responses, and extracted action items."
                }
        
        # Default response
        return {
            "content": "I've processed your request. Based on the available tools and data, the task has been completed."
        }
    
    async def simple_completion(
        self,
        prompt: str,
        model: Optional[str] = None,
        complexity: Optional[ModelComplexity] = None,
        max_tokens: int = 1000
    ) -> str:
        """
        Simple text completion without tools.
        
        Args:
            prompt: The prompt
            model: Specific model to use (optional)
            complexity: Model complexity level (used if model not specified)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        # Select model based on complexity if not explicitly provided
        if not model and complexity:
            model_config = ai_model_router.select_model(complexity)
            model = model_config.model_id
            logger.info(f"Selected model {model_config.name} for complexity {complexity}")
        elif not model:
            # Default to SIMPLE complexity
            model_config = ai_model_router.select_model(ModelComplexity.SIMPLE)
            model = model_config.model_id
        
        messages = [{"role": "user", "content": prompt}]
        response = await self._call_llm_with_tools(messages, [], model)
        return response.get("content", "")

# Global instance
llm_service = LLMService()