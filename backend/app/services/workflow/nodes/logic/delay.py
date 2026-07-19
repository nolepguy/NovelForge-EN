import asyncio
from typing import Any, AsyncIterator
from pydantic import BaseModel, Field
from loguru import logger

from ...registry import register_node
from ..base import BaseNode


class LogicDelayInput(BaseModel):
    """Delay input"""
    input: Any = Field(None, description="Input data (passthrough)")
    seconds: float = Field(1.0, description="Delay in seconds")


class LogicDelayOutput(BaseModel):
    """Delay output"""
    output: Any = Field(None, description="Output data (passthrough)")


@register_node
class LogicDelayNode(BaseNode[LogicDelayInput, LogicDelayOutput]):
    node_type = "Logic.Delay"
    category = "logic"
    label = "Delay"
    description = "Continue after delaying for a specified duration"
    
    input_model = LogicDelayInput
    output_model = LogicDelayOutput

    async def execute(self, inputs: LogicDelayInput) -> AsyncIterator[LogicDelayOutput]:
        """Delay node"""
        logger.info(f"[Delay] Delaying {inputs.seconds} seconds")
        await asyncio.sleep(inputs.seconds)
        
        yield LogicDelayOutput(output=inputs.input)