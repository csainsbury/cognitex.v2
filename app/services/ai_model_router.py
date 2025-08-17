"""
AI Model Router for selecting appropriate models based on task complexity
"""
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

class ModelComplexity(str, Enum):
    """Model complexity levels for task routing"""
    SIMPLE = "simple"      # Quick, low-cost tasks (Claude Haiku)
    MEDIUM = "medium"      # Standard tasks (Claude Sonnet)
    COMPLEX = "complex"    # Deep analysis tasks (Claude Opus)

class AnthropicModel(str, Enum):
    """Available Anthropic models"""
    HAIKU = "claude-3-haiku-20240307"
    SONNET = "claude-3-5-sonnet-20241022"
    OPUS = "claude-3-opus-20240229"

@dataclass
class ModelConfig:
    """Configuration for a model"""
    name: str
    model_id: str
    max_tokens: int
    temperature: float
    cost_per_1k_input: float  # in USD
    cost_per_1k_output: float  # in USD

class AIModelRouter:
    """
    Routes AI requests to appropriate models based on complexity and cost.
    Currently supports Anthropic models only.
    """
    
    def __init__(self):
        """Initialize the model router with available models"""
        self.models: Dict[ModelComplexity, ModelConfig] = {
            ModelComplexity.SIMPLE: ModelConfig(
                name="Claude Haiku",
                model_id=AnthropicModel.HAIKU,
                max_tokens=4096,
                temperature=0.3,
                cost_per_1k_input=0.00025,
                cost_per_1k_output=0.00125
            ),
            ModelComplexity.MEDIUM: ModelConfig(
                name="Claude Sonnet",
                model_id=AnthropicModel.SONNET,
                max_tokens=8192,
                temperature=0.5,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015
            ),
            ModelComplexity.COMPLEX: ModelConfig(
                name="Claude Opus",
                model_id=AnthropicModel.OPUS,
                max_tokens=4096,
                temperature=0.7,
                cost_per_1k_input=0.015,
                cost_per_1k_output=0.075
            )
        }
        
        # Track usage for cost monitoring
        self.usage_stats: Dict[str, Dict[str, int]] = {}
        
        logger.info("AI Model Router initialized with Anthropic models")
    
    def select_model(
        self,
        complexity: ModelComplexity,
        task_type: Optional[str] = None
    ) -> ModelConfig:
        """
        Select the appropriate model based on complexity and task type.
        
        Args:
            complexity: Required complexity level
            task_type: Optional task type for specialized routing
            
        Returns:
            ModelConfig for the selected model
        """
        # Special routing based on task type
        if task_type:
            if task_type == "email_triage" and complexity == ModelComplexity.COMPLEX:
                # Use medium model for email triage to save costs
                logger.info(f"Downgrading from COMPLEX to MEDIUM for {task_type}")
                complexity = ModelComplexity.MEDIUM
            elif task_type == "synthesis" and complexity == ModelComplexity.SIMPLE:
                # Always use at least medium for synthesis tasks
                logger.info(f"Upgrading from SIMPLE to MEDIUM for {task_type}")
                complexity = ModelComplexity.MEDIUM
        
        model_config = self.models[complexity]
        logger.debug(f"Selected {model_config.name} for complexity {complexity}")
        
        return model_config
    
    def estimate_cost(
        self,
        complexity: ModelComplexity,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Estimate the cost of a model call.
        
        Args:
            complexity: Model complexity level
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        model = self.models[complexity]
        
        input_cost = (input_tokens / 1000) * model.cost_per_1k_input
        output_cost = (output_tokens / 1000) * model.cost_per_1k_output
        
        total_cost = input_cost + output_cost
        
        return total_cost
    
    def track_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        task_type: Optional[str] = None
    ) -> None:
        """
        Track model usage for monitoring and optimization.
        
        Args:
            model_id: The model that was used
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            task_type: Optional task type for categorization
        """
        if model_id not in self.usage_stats:
            self.usage_stats[model_id] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_calls": 0
            }
        
        stats = self.usage_stats[model_id]
        stats["total_input_tokens"] += input_tokens
        stats["total_output_tokens"] += output_tokens
        stats["total_calls"] += 1
        
        # Track by task type if provided
        if task_type:
            task_key = f"task_{task_type}_calls"
            stats[task_key] = stats.get(task_key, 0) + 1
        
        logger.debug(f"Tracked usage for {model_id}: +{input_tokens} input, +{output_tokens} output")
    
    def get_usage_report(self) -> Dict[str, Any]:
        """
        Get a usage report with costs.
        
        Returns:
            Dictionary with usage statistics and estimated costs
        """
        report = {
            "models": {},
            "total_cost": 0.0
        }
        
        for model_id, stats in self.usage_stats.items():
            # Find model config by ID
            model_config = None
            for config in self.models.values():
                if config.model_id == model_id:
                    model_config = config
                    break
            
            if model_config:
                cost = self.estimate_cost(
                    next(k for k, v in self.models.items() if v.model_id == model_id),
                    stats["total_input_tokens"],
                    stats["total_output_tokens"]
                )
                
                report["models"][model_id] = {
                    "name": model_config.name,
                    "usage": stats,
                    "estimated_cost": cost
                }
                report["total_cost"] += cost
        
        return report
    
    def get_recommended_model(
        self,
        prompt_length: int,
        expected_output_length: int,
        max_budget: Optional[float] = None
    ) -> ModelComplexity:
        """
        Recommend a model based on token counts and budget.
        
        Args:
            prompt_length: Estimated prompt length in characters
            expected_output_length: Expected output length in characters
            max_budget: Maximum budget in USD (optional)
            
        Returns:
            Recommended ModelComplexity level
        """
        # Rough token estimation (1 token ≈ 4 characters)
        input_tokens = prompt_length // 4
        output_tokens = expected_output_length // 4
        
        # Start with the most complex model and work down
        for complexity in [ModelComplexity.COMPLEX, ModelComplexity.MEDIUM, ModelComplexity.SIMPLE]:
            if max_budget:
                cost = self.estimate_cost(complexity, input_tokens, output_tokens)
                if cost <= max_budget:
                    logger.info(f"Recommended {complexity} model within budget ${max_budget:.4f}")
                    return complexity
            else:
                # Without budget constraint, use heuristics
                total_tokens = input_tokens + output_tokens
                if total_tokens < 1000:
                    return ModelComplexity.SIMPLE
                elif total_tokens < 4000:
                    return ModelComplexity.MEDIUM
                else:
                    return ModelComplexity.COMPLEX
        
        # Default to simplest model if budget is very tight
        return ModelComplexity.SIMPLE

# Global instance
ai_model_router = AIModelRouter()