"""
LLM Service - Generic wrapper for LLM API providers
This service provides a stateless interface to LLM providers without domain-specific logic.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from app.config import settings
from app.services.ai_model_router import ModelComplexity, model_router

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    
class LLMService:
    """
    Service for interacting with Large Language Models.
    This is a stateless, generic service that passes requests to LLM providers.
    All domain-specific logic should be in the agents, not here.
    """
    
    def __init__(self):
        """Initialize LLM service with available providers"""
        self.anthropic_client = None
        self.openai_client = None
        
        # Initialize Anthropic client if API key is available
        if settings.ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic
                self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
        
        # Initialize OpenAI client if API key is available
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
    
    async def simple_completion(
        self,
        prompt: str,
        complexity: ModelComplexity = ModelComplexity.SIMPLE,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> str:
        """
        Simple text completion without tools.
        
        Args:
            prompt: The prompt to send to the LLM
            complexity: Model complexity level for router
            max_tokens: Maximum tokens in response
            temperature: Temperature for response generation
            
        Returns:
            The text response from the LLM
        """
        model = model_router.select_model(complexity)
        
        messages = [{"role": "user", "content": prompt}]
        
        if self.anthropic_client and model.provider == "anthropic":
            try:
                response = self.anthropic_client.messages.create(
                    model=model.model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages
                )
                return response.content[0].text
            except Exception as e:
                logger.error(f"Anthropic API error: {e}")
                return f"Error: {str(e)}"
        
        elif self.openai_client and model.provider == "openai":
            try:
                response = self.openai_client.chat.completions.create(
                    model=model.model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                return f"Error: {str(e)}"
        
        return "No LLM provider available"
    
    async def execute_with_tools(
        self,
        prompt: str,
        tools: Dict[str, Callable],
        complexity: ModelComplexity = ModelComplexity.MEDIUM,
        max_iterations: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute prompt with access to tools.
        
        Args:
            prompt: The initial prompt
            tools: Dictionary of tool name to callable
            complexity: Model complexity level
            max_iterations: Maximum tool-use iterations
            **kwargs: Additional arguments to pass to tools
            
        Returns:
            Dictionary with response and tool history
        """
        model = model_router.select_model(complexity)
        
        # Convert tools to API format
        tool_schemas = self._build_tool_schemas(tools)
        
        # Initialize conversation
        messages = [{"role": "user", "content": prompt}]
        tool_history = []
        
        for iteration in range(max_iterations):
            # Call LLM with tools
            if self.anthropic_client and model.provider == "anthropic":
                response = await self._call_anthropic_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    model=model.model_id
                )
            elif self.openai_client and model.provider == "openai":
                response = await self._call_openai_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    model=model.model_id
                )
            else:
                return {
                    "response": "No LLM provider available",
                    "tool_history": [],
                    "iterations": 0
                }
            
            # Process response
            if "tool_calls" in response:
                # Execute tools
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("arguments", {})
                    
                    if tool_name in tools:
                        try:
                            # Add kwargs to tool arguments
                            tool_args.update(kwargs)
                            result = tools[tool_name](**tool_args)
                            
                            tool_history.append({
                                "tool": tool_name,
                                "arguments": tool_args,
                                "result": result
                            })
                            
                            # Add tool result to conversation
                            messages.append({
                                "role": "assistant",
                                "content": f"I'll use the {tool_name} tool."
                            })
                            messages.append({
                                "role": "user",
                                "content": f"Tool result: {json.dumps(result, default=str)[:5000]}"  # Limit size
                            })
                            
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {e}")
                            messages.append({
                                "role": "user",
                                "content": f"Tool error: {str(e)}"
                            })
                    else:
                        logger.error(f"Unknown tool requested: {tool_name}")
            else:
                # LLM provided final answer
                return {
                    "response": response.get("content", ""),
                    "final_response": response.get("content", ""),
                    "tool_history": tool_history,
                    "tool_calls": len(tool_history),
                    "iterations": iteration + 1
                }
        
        return {
            "response": "Max iterations reached",
            "tool_history": tool_history,
            "iterations": max_iterations
        }
    
    async def _call_anthropic_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: str
    ) -> Dict[str, Any]:
        """
        Pure passthrough to Anthropic API with tool support.
        No domain-specific logic should be here.
        """
        if not self.anthropic_client:
            logger.error("Anthropic client not initialized")
            return {"content": "Anthropic client not available"}
        
        try:
            # Convert tool schemas to Anthropic format
            anthropic_tools = []
            for tool in tools:
                anthropic_tool = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool.get("parameters", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
                anthropic_tools.append(anthropic_tool)
            
            # Separate system message from conversation
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append(msg)
            
            # Make the API call - pure passthrough
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_message,
                messages=anthropic_messages,
                tools=anthropic_tools if anthropic_tools else None,
                tool_choice={"type": "auto"} if anthropic_tools else None
            )
            
            # Parse response
            result = {}
            
            # Check for tool use
            if hasattr(response, 'content') and response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'type'):
                        if content_block.type == 'text':
                            result["content"] = content_block.text
                        elif content_block.type == 'tool_use':
                            if "tool_calls" not in result:
                                result["tool_calls"] = []
                            result["tool_calls"].append({
                                "name": content_block.name,
                                "arguments": content_block.input
                            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return {"content": f"API Error: {str(e)}"}
    
    async def _call_openai_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: str
    ) -> Dict[str, Any]:
        """
        Pure passthrough to OpenAI API with tool support.
        """
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return {"content": "OpenAI client not available"}
        
        try:
            # Convert tools to OpenAI format
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("parameters", {})
                    }
                })
            
            # Make the API call
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None
            )
            
            # Parse response
            result = {}
            choice = response.choices[0]
            
            if choice.message.content:
                result["content"] = choice.message.content
            
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                result["tool_calls"] = []
                for tool_call in choice.message.tool_calls:
                    result["tool_calls"].append({
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {"content": f"API Error: {str(e)}"}
    
    def _build_tool_schemas(self, tools: Dict[str, Callable]) -> List[Dict]:
        """
        Build tool schemas from callable functions.
        """
        schemas = []
        
        for name, func in tools.items():
            # Extract schema from function docstring and annotations
            schema = {
                "name": name,
                "description": func.__doc__ or f"Tool: {name}",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            
            # Try to extract parameters from function annotations
            import inspect
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param_name not in ['self', 'cls']:
                    param_schema = {"type": "string"}  # Default type
                    
                    # Try to infer type from annotation
                    if param.annotation != inspect.Parameter.empty:
                        if param.annotation == int:
                            param_schema["type"] = "integer"
                        elif param.annotation == bool:
                            param_schema["type"] = "boolean"
                        elif param.annotation == float:
                            param_schema["type"] = "number"
                    
                    schema["parameters"]["properties"][param_name] = param_schema
                    
                    # Mark as required if no default value
                    if param.default == inspect.Parameter.empty:
                        schema["parameters"]["required"].append(param_name)
            
            schemas.append(schema)
        
        return schemas

# Create singleton instance
llm_service = LLMService()