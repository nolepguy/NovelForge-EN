from typing import Any, Dict, AsyncIterator
from pydantic import Field, BaseModel
from loguru import logger

from ...registry import register_node
from ..base import BaseNode
from ...expressions import evaluate_expression


class LogicAssertInput(BaseModel):
    """Assert node input"""
    condition: str = Field(..., description="Assertion condition expression")
    message: str = Field("Assertion failed", description="Error message on failure")


class LogicAssertOutput(BaseModel):
    """Assert node output (empty)"""
    pass


@register_node
class LogicAssertNode(BaseNode[LogicAssertInput, LogicAssertOutput]):
    """Assert node
    
    Verifies that a condition is true; if false, stops workflow execution.
    Used to replace the Logic.End node, implementing condition validation and early exit.
    """
    node_type = "Logic.Assert"
    category = "logic"
    label = "Assert"
    description = "Validate a condition; stop the workflow on failure"
    
    input_model = LogicAssertInput
    output_model = LogicAssertOutput

    async def execute(self, inputs: LogicAssertInput) -> AsyncIterator[LogicAssertOutput]:
        """Execute assertion validation"""
        try:
            # Prepare the evaluation environment
            eval_context = {
                **self.context.variables
            }
            
            # Evaluate the condition expression
            result = evaluate_expression(inputs.condition, eval_context)
            is_true = bool(result)
            
            if not is_true:
                # Assertion failed, raise an exception
                logger.error(f"[Assert] Assertion failed: {inputs.condition} - {inputs.message}")
                raise AssertionError(f"Assertion failed: {inputs.message}")
            
            # Assertion passed, continue execution
            logger.info(f"[Assert] Assertion passed: {inputs.condition}")
            yield LogicAssertOutput()
        
        except Exception as e:
            if isinstance(e, AssertionError):
                raise
            logger.error(f"[Assert] Condition evaluation failed: {e}")
            raise ValueError(f"Assertion condition evaluation failed: {str(e)}")