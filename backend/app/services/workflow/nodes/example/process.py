"""Example node - demonstrates the new BaseNode interface usage

Includes examples of progress push and streaming execution.
"""

from typing import List, Dict, Any, AsyncIterator, Union, TYPE_CHECKING
from pydantic import BaseModel, Field
from loguru import logger
import asyncio

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from ..base import BaseNode
from ...registry import register_node


# ============= Example.Process node =============

class ExampleProcessInput(BaseModel):
    """Example process node input"""
    items: List[str] = Field(..., description="List of items to process")
    delay: float = Field(0.5, description="Processing delay per item (seconds)", ge=0.0, le=10.0)
    enable_progress: bool = Field(True, description="Whether to enable progress push")


class ExampleProcessOutput(BaseModel):
    """Example process node output"""
    results: List[Dict[str, Any]] = Field(..., description="Processing result list")
    summary: Dict[str, Any] = Field(..., description="Processing summary")


@register_node
class ExampleProcessNode(BaseNode[ExampleProcessInput, ExampleProcessOutput]):
    """Example process node

    Demonstrates how to use the new BaseNode interface:
    1. Use Pydantic input/output models
    2. Implement streaming execution and progress push
    3. Type-safe input and output
    """

    node_type = "Example.Process"
    category = "example"
    label = "Example Process"
    description = "Process an item list and push progress (for testing and demonstration)"

    input_model = ExampleProcessInput
    output_model = ExampleProcessOutput

    async def execute(self, inputs: ExampleProcessInput) -> AsyncIterator[Union['ProgressEvent', ExampleProcessOutput]]:
        """Streaming execution method (supports progress push and checkpoint recovery)
        
        Checkpoint recovery mechanism:
        1. Read the previous progress from self.context.checkpoint
        2. Continue processing from the interrupted position
        3. Save checkpoint data on each progress update
        """
        from ...engine.async_executor import ProgressEvent
        
        logger.info(f"[Example.Process] Starting to process {len(inputs.items)} items")

        # === 1. Read the checkpoint (auto-injected) ===
        checkpoint = getattr(self.context, 'checkpoint', None)
        start_index = checkpoint.get('processed_count', 0) if checkpoint else 0
        
        if start_index > 0:
            logger.info(f"[Example.Process] Resumed from checkpoint: processed {start_index}/{len(inputs.items)}")

        results = []
        total = len(inputs.items)
        
        # === 2. Continue processing from the checkpoint ===
        for i in range(start_index, total):
            item = inputs.items[i]
            
            # Simulate processing
            await asyncio.sleep(inputs.delay)
            result = {"item": item, "processed": True, "index": i}
            results.append(result)
            
            # === 3. Report progress (auto-saves checkpoint) ===
            if inputs.enable_progress:
                percent = ((i + 1) / total) * 100
                yield ProgressEvent(
                    percent=percent,
                    message=f"Processing: {item} ({i+1}/{total})",
                    data={
                        'processed_count': i + 1,  # Lightweight: counter
                        'last_item': item          # Lightweight: identifier
                    }
                )

        summary = {
            "total": len(inputs.items),
            "processed": len(results),
            "success_rate": 1.0
        }

        logger.info(f"[Example.Process] Processing completed: {summary}")

        # === 4. Return the final result ===
        yield ExampleProcessOutput(
            results=results,
            summary=summary
        )

class BatchProcessInput(BaseModel):
    """Batch process node input"""
    data: List[Any] = Field(..., description="List of data to process")
    batch_size: int = Field(10, description="Batch size", ge=1, le=100)
    parallel: bool = Field(False, description="Whether to process batches in parallel")


class BatchProcessOutput(BaseModel):
    """Batch process node output"""
    results: List[Dict[str, Any]] = Field(..., description="Processing result list")
    total_processed: int = Field(..., description="Total processed count")


@register_node
class BatchProcessNode(BaseNode[BatchProcessInput, BatchProcessOutput]):
    """Batch process node

    Demonstrates batch processing and parallel execution.
    """

    node_type = "Example.BatchProcess"
    category = "example"
    label = "Batch Process"
    description = "Batch process data, supports parallelism (for testing and demonstration)"

    input_model = BatchProcessInput
    output_model = BatchProcessOutput

    async def execute(self, inputs: BatchProcessInput) -> AsyncIterator[BatchProcessOutput]:
        """Batch processing execution"""
        logger.info(f"[Example.BatchProcess] Processing {len(inputs.data)} records, batch size: {inputs.batch_size}")

        results = []

        # Process in batches
        for i in range(0, len(inputs.data), inputs.batch_size):
            batch = inputs.data[i:i + inputs.batch_size]

            if inputs.parallel:
                # Process batches in parallel
                tasks = [self._process_item(item) for item in batch]
                batch_results = await asyncio.gather(*tasks)
            else:
                # Process batches serially
                batch_results = []
                for item in batch:
                    result = await self._process_item(item)
                    batch_results.append(result)

            results.extend(batch_results)

        logger.info(f"[Example.BatchProcess] Processing completed: {len(results)} results")

        yield BatchProcessOutput(
            results=results,
            total_processed=len(results)
        )

    async def _process_item(self, item: Any) -> Dict[str, Any]:
        """Process a single item"""
        await asyncio.sleep(0.1)  # Simulate processing
        return {"item": item, "processed": True}