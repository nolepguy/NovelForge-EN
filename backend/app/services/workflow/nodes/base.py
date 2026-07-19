"""Node base class and utility functions

Minimal type-safe design:
1. Only Input and Output models are needed, no Config required
2. Fully leverage Pydantic's type validation and JSON Schema
3. The execute method directly receives and returns Pydantic models
4. Metadata is automatically generated from the models
"""

from typing import Any, Dict, Optional, List, Type, Union, AsyncIterator, Generic, TypeVar, TYPE_CHECKING
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from typing_extensions import ClassVar
from abc import ABC, abstractmethod
import inspect
import asyncio

if TYPE_CHECKING:
    from ..engine.async_executor import ProgressEvent

from app.db.models import Card, CardType
from ..types import ExecutionContext, NodeMetadata


# Type variables
TInput = TypeVar('TInput', bound=BaseModel)
TOutput = TypeVar('TOutput', bound=BaseModel)


def get_card_by_id(session: Session, card_id: int) -> Optional[Card]:
    """Get a card by ID"""
    return session.get(Card, card_id)


def get_card_type_by_name(session: Session, type_name: str) -> Optional[CardType]:
    """Get a card type by name"""
    stmt = select(CardType).where(CardType.name == type_name)
    return session.exec(stmt).first()


def resolve_card_reference(
    session: Session,
    reference: Any,
    context_card_id: Optional[int] = None
) -> Optional[Card]:
    """Resolve a card reference

    Supported reference formats:
    - Number: used directly as the card ID
    - "$self": the current context card
    - "$parent": the parent card
    - Dict {"id": 123}: explicitly specify the ID

    Args:
        session: Database session
        reference: Card reference
        context_card_id: Context card ID (used for references like $self)

    Returns:
        Card object, or None if it does not exist
    """
    # A number is used directly as the ID
    if isinstance(reference, int):
        return get_card_by_id(session, reference)

    # String reference
    if isinstance(reference, str):
        if reference == "$self" and context_card_id:
            return get_card_by_id(session, context_card_id)
        elif reference == "$parent" and context_card_id:
            card = get_card_by_id(session, context_card_id)
            if card and card.parent_id:
                return get_card_by_id(session, card.parent_id)

    # Dict reference
    if isinstance(reference, dict):
        card_id = reference.get("id")
        if card_id:
            return get_card_by_id(session, card_id)

    return None


class BaseNode(ABC, Generic[TInput, TOutput]):
    """Node base class - minimal type-safe design
    
    Usage example:
    ```python
    class NovelLoadInput(BaseModel):
        root_path: str = Field(..., description="Novel root directory")
        file_pattern: str = Field(r".*\\.txt$", description="File matching")
    
    class NovelLoadOutput(BaseModel):
        chapter_list: List[Dict] = Field(..., description="Chapter list")
        volume_list: List[str] = Field(..., description="Volume list")
    
    @register_node
    class NovelLoadNode(BaseNode[NovelLoadInput, NovelLoadOutput]):
        node_type = "Novel.Load"
        category = "novel"
        label = "Load Novel"
        description = "Scan novel directory"
        
        input_model = NovelLoadInput
        output_model = NovelLoadOutput
        
        async def execute(self, inputs: NovelLoadInput) -> NovelLoadOutput:
            # Use the typed input directly
            chapters = scan_directory(inputs.root_path)
            
            # Return the typed output directly
            return NovelLoadOutput(
                chapter_list=chapters,
                volume_list=volumes
            )
    ```
    """
    
    # Metadata (subclasses must define)
    node_type: ClassVar[str]
    category: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str] = ""
    
    # Input/output models (subclasses must define)
    input_model: ClassVar[Type[TInput]]
    output_model: ClassVar[Type[TOutput]]

    @classmethod
    def get_output_schema_contract(
        cls,
        config: Dict[str, Any],
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the structured schema contract of the node output (optional).

        Used for static validation of scenarios such as
        "node output object passed directly to card content".
        No contract by default; specific nodes may override as needed.
        """
        return None
    
    def __init__(self, context: ExecutionContext):
        """Initialize the node
        
        Args:
            context: Execution context (contains session, variables, etc.)
        """
        self.context = context
        self._cleanup_tasks: List[Any] = []  # List of tasks to clean up
    
    async def cleanup(self):
        """Clean up node resources
        
        Called when the workflow is paused or cancelled, to clean up resources inside the node:
        - Cancel running subtasks
        - Close file handles
        - Release database connections
        - Clean up temporary files
        
        Subclasses can override this method to implement custom cleanup logic.
        
        Default implementation: cancels all tasks registered via register_task().
        """
        if self._cleanup_tasks:
            from loguru import logger
            logger.info(f"[{self.node_type}] Cleaning up {len(self._cleanup_tasks)} tasks")
            
            for task in self._cleanup_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass  # Normal cancellation
                    except Exception as e:
                        logger.error(f"[{self.node_type}] Error while cancelling task: {e}")
            
            self._cleanup_tasks.clear()
    
    def register_task(self, task):
        """Register a task to be cleaned up
        
        Async tasks created inside a node should be registered via this method,
        so they can be correctly cancelled when the workflow is paused.
        
        Args:
            task: asyncio.Task object
        """
        self._cleanup_tasks.append(task)
    
    @classmethod
    def get_metadata(cls) -> NodeMetadata:
        """Get node metadata
        
        Automatically generates the full JSON Schema from the Pydantic models.
        
        Returns:
            NodeMetadata object
        """
        # Input Schema (auto-generated from Pydantic)
        input_schema = {}
        if hasattr(cls, 'input_model') and cls.input_model:
            input_schema = cls.input_model.model_json_schema()
        
        # Output Schema (auto-generated from Pydantic)
        output_schema = {}
        if hasattr(cls, 'output_model') and cls.output_model:
            output_schema = cls.output_model.model_json_schema()
        
        return NodeMetadata(
            type=cls.node_type,
            category=cls.category,
            label=cls.label,
            description=cls.description,
            documentation=inspect.getdoc(cls) or "",
            input_schema=input_schema,
            output_schema=output_schema,
            executor=cls
        )
    
    @abstractmethod
    async def execute(self, inputs: TInput) -> AsyncIterator[Union['ProgressEvent', TOutput]]:
        """Execute node logic (unified streaming interface)
        
        The node can yield two types:
        1. ProgressEvent: report progress (optional, used for batch processing)
        2. TOutput: the final result (required, yield at least once)
        
        Args:
            inputs: Typed input model
            
        Yields:
            ProgressEvent: progress event (optional, used for batch processing)
            TOutput: output model instance (required, yield at least once)
            
        Notes:
        - Simple nodes: only yield the result, zero extra code
        - Batch processing nodes: can yield ProgressEvent multiple times to report progress, then yield the result last
        - The last yielded TOutput is used as the node's output
        
        Example:
            # Simple node (only yields the result)
            async def execute(self, inputs):
                result = await process(inputs)
                yield Output(result=result)
            
            # Batch processing node (yields progress + result)
            async def execute(self, inputs):
                for i, item in enumerate(inputs.items):
                    result = await process(item)
                    
                    # Report progress (auto-saves checkpoint)
                    yield ProgressEvent(
                        percent=(i + 1) / len(inputs.items) * 100,
                        message=f"Processed {i + 1}/{len(inputs.items)}"
                    )
                
                # Return the final result
                yield Output(results=results)
        
        Raises:
            Exception: raised when execution fails
        """
        raise NotImplementedError


# --- Convenience base classes ---

class NoInputNode(BaseNode[BaseModel, TOutput]):
    """Convenience base class for nodes without input
    
    Used for nodes that do not need input parameters (such as triggers).
    """
    
    class EmptyInput(BaseModel):
        """Empty input"""
        pass
    
    input_model = EmptyInput
    
    async def execute(self, inputs: BaseModel) -> AsyncIterator[Union['ProgressEvent', TOutput]]:
        """Execute the node (ignores input)"""
        result = await self.execute_no_input()
        yield result
    
    @abstractmethod
    async def execute_no_input(self) -> TOutput:
        """Execution method without input"""
        raise NotImplementedError


class NoOutputNode(BaseNode[TInput, BaseModel]):
    """Convenience base class for nodes without output
    
    Used for nodes that only have side effects and do not return data (such as logs, display).
    """
    
    class EmptyOutput(BaseModel):
        """Empty output"""
        pass
    
    output_model = EmptyOutput
    
    async def execute(self, inputs: TInput) -> AsyncIterator[Union['ProgressEvent', BaseModel]]:
        """Execute the node (no return value)"""
        await self.execute_no_output(inputs)
        yield self.EmptyOutput()
    
    @abstractmethod
    async def execute_no_output(self, inputs: TInput) -> None:
        """Execution method without output"""
        raise NotImplementedError


# --- Utility functions ---