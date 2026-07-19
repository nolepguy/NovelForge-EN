from typing import Any, Dict, List, Optional, AsyncIterator, Union, TYPE_CHECKING
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.orm.attributes import flag_modified

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from app.db.models import Card
from app.services.card_service import CardService
from app.schemas.card import CardCreate
from ...registry import register_node
from ..base import BaseNode, get_card_type_by_name


class CardBatchUpsertInput(BaseModel):
    """Batch upsert card input"""
    project_id: int = Field(..., description="Project ID (must be passed explicitly)")
    items: List[Any] = Field(..., description="Data list (must be a list type)")
    card_type: str = Field(
        ..., 
        description="Card type name",
        json_schema_extra={"x-component": "CardTypeSelect"}
    )
    title_template: str = Field(..., description="Title template, supports {item.field} syntax")
    content_template: Optional[Any] = Field(default_factory=dict, description="Content template (optional, supports dict or str)")
    match_by: str = Field("title", description="How to match existing cards (default by title)")
    parent_id: Optional[Any] = Field(None, description="Parent card ID (supports an ID number or template syntax {item.pid})")


class CardBatchUpsertOutput(BaseModel):
    """Batch upsert card output"""
    cards: List[Dict[str, Any]] = Field(..., description="List of processed cards")
    output: List[int] = Field(..., description="Card ID list (compatibility)")


@register_node
class CardBatchUpsertNode(BaseNode[CardBatchUpsertInput, CardBatchUpsertOutput]):
    """Batch create/update card node.

    Strict constraints (for the workflow authoring Agent):
    1) `content_template` must be a literal dict, with fields aligned to the target card schema.
    2) `{item.xxx}` placeholders are allowed in field values; setting the whole
       `content_template` to an expression result is forbidden.
    3) Do not fabricate fields; confirm the writable fields of the card type first.

    Recommended: query the card type schema first, then author `title_template/content_template`.
    """
    node_type = "Card.BatchUpsert"
    category = "card"
    label = "Batch Upsert Cards"
    description = "Batch create or update cards based on a list of data"
    
    input_model = CardBatchUpsertInput
    output_model = CardBatchUpsertOutput

    async def execute(self, inputs: CardBatchUpsertInput) -> AsyncIterator[Union['ProgressEvent', CardBatchUpsertOutput]]:
        """Batch upsert cards (supports checkpoint recovery)"""
        from ...engine.async_executor import ProgressEvent
        
        items = inputs.items
        
        # Require the input to be a list
        if not isinstance(items, list):
            raise ValueError(f"items input must be a list type, current type: {type(items).__name__}. Please use the Data.ExtractPath node to extract a list.")
        
        # === 1. Read checkpoint ===
        checkpoint = getattr(self.context, 'checkpoint', None)
        start_index = checkpoint.get('processed_count', 0) if checkpoint else 0
        
        if start_index > 0:
            logger.info(f"[BatchUpsert] Resumed from checkpoint: processed {start_index}/{len(items)}")
        
        # Get the base parent_id config
        base_parent_id = inputs.parent_id
        
        # Compatibility handling: if parent_id is a dict (from Card.Read output), extract id
        if isinstance(base_parent_id, dict):
            base_parent_id = base_parent_id.get("id")
        
        # Get the card type
        card_type = get_card_type_by_name(self.context.session, inputs.card_type)
        if not card_type:
            raise ValueError(f"Card type does not exist: {inputs.card_type}")

        # Use the explicitly passed project_id (no longer looked up from global variables)
        project_id = inputs.project_id
        
        logger.info(
            f"[BatchUpsert] Using explicitly passed project ID: project_id={project_id}"
        )

        results = []
        service = CardService(self.context.session)
        total = len(items)
        
        # === 2. Continue processing from the checkpoint ===
        for index in range(start_index, total):
            item = items[index]
            
            # Prepare the template context
            ctx = {"item": item, "index": index + 1}
            
            # Render the title
            try:
                title = self._render_template(inputs.title_template, ctx)
            except Exception as e:
                logger.warning(f"[BatchUpsert] Title rendering failed: {e}")
                continue
                
            if not title:
                continue

            # Compute the current item's parent_id
            current_parent_id = None
            if base_parent_id is not None:
                if isinstance(base_parent_id, int):
                    current_parent_id = base_parent_id
                elif isinstance(base_parent_id, str):
                    if '{' in base_parent_id and '}' in base_parent_id:
                        # Template rendering
                        rendered = self._render_template(base_parent_id, ctx)
                        # Try to convert to int
                        if rendered and rendered.isdigit():
                            current_parent_id = int(rendered)
                        else:
                            # Rendered result is empty or non-numeric; treat as no parent or invalid
                            current_parent_id = None 
                    elif base_parent_id.isdigit():
                         current_parent_id = int(base_parent_id)
            
            # Find the existing card
            stmt = select(Card).where(
                Card.project_id == project_id,
                Card.card_type_id == card_type.id,
                Card.title == title
            )
            if current_parent_id:
                stmt = stmt.where(Card.parent_id == current_parent_id)
            
            existing_card = self.context.session.exec(stmt).first()
            
            # Render the content
            content = {}
            if inputs.content_template:
                rendered_content = self._render_content(inputs.content_template, ctx)
                # Ensure content is a dict type
                if isinstance(rendered_content, dict):
                    content = rendered_content
                elif rendered_content:  # Non-empty but not a dict, wrap as a dict
                    content = {"value": rendered_content}
                # If it is an empty string or None, keep content as an empty dict
            elif isinstance(item, dict):
                 # If there is no template and item is a dict, use item as content by default
                 content = item
            
            if existing_card:
                # Update
                updated = False
                if content:
                    # Simple merge
                    if not isinstance(existing_card.content, dict):
                        existing_card.content = {}
                    existing_card.content.update(content)
                    flag_modified(existing_card, "content")
                    updated = True
                
                # If the parent ID changed (moved)
                if current_parent_id and existing_card.parent_id != current_parent_id:
                    existing_card.parent_id = current_parent_id
                    updated = True
                    
                if updated:
                    self.context.session.add(existing_card)
                    # Manually commit the update
                    self.context.session.commit()
                    self.context.session.refresh(existing_card)
                    results.append(existing_card)
                else:
                    results.append(existing_card)
            else:
                # Create
                try:
                    card_create = CardCreate(
                        title=title,
                        content=content,
                        card_type_id=card_type.id,
                        parent_id=current_parent_id,
                        project_id=project_id
                    )
                    
                    new_card = service.create(card_create, project_id)
                    results.append(new_card)
                except Exception as e:
                    logger.error(f"[BatchUpsert] Failed to create card: {e}")
                    continue
            
            # === 3. Report progress (auto-saves checkpoint) ===
            percent = ((index + 1) / total) * 100
            yield ProgressEvent(
                percent=percent,
                message=f"Processed {index + 1}/{total} cards",
                data={
                    'processed_count': index + 1,  # Lightweight: counter
                    'last_title': title            # Lightweight: identifier
                }
            )
        
        self.context.session.commit()
        
        # Refresh to get IDs
        touched = self.context.variables.setdefault("touched_card_ids", [])
        for card in results:
            self.context.session.refresh(card)
            if card.id not in touched:
                touched.append(card.id)

        logger.info(f"[BatchUpsert] Batch processing completed: {len(results)} cards ({inputs.card_type})")
        
        # === 4. Return the final result ===
        yield CardBatchUpsertOutput(
            cards=[
                {
                    "id": c.id,
                    "title": c.title,
                    "content": c.content,
                    "parent_id": c.parent_id
                } for c in results
            ],
            output=[c.id for c in results]  # Compatibility output
        )

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Simple string template rendering {a.b}"""
        # Simple implementation, supports {item.field}
        # For more complex needs jinja2 could be used; here a simple hand-written one
        import re
        
        def replace(match):
            path = match.group(1).strip()
            # Parse the path item.name
            parts = path.split('.')
            value = context
            try:
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part)
                    else:
                        value = None
                        break
                return str(value) if value is not None else ""
            except Exception:
                return ""

        return re.sub(r'\{([^}]+)\}', replace, template)

    def _render_content(self, template: Any, context: Dict[str, Any]) -> Any:
        "Recursively render content"
        if isinstance(template, str):
            # Only attempt rendering when it contains {}
            if '{' in template and '}' in template:
                # Special handling: if it is a single path reference (e.g. {item.ai_result}), return the original object
                import re
                single_path_match = re.fullmatch(r'\{([^}]+)\}', template)
                if single_path_match:
                    path = single_path_match.group(1).strip()
                    parts = path.split('.')
                    value = context
                    try:
                        for part in parts:
                            if isinstance(value, dict):
                                value = value.get(part)
                            elif hasattr(value, part):
                                value = getattr(value, part)
                            else:
                                value = None
                                break
                        # If parsing succeeds, return the original object
                        if value is not None:
                            return value
                    except Exception:
                        pass
                
                # Fallback: normal string rendering
                return self._render_template(template, context)
            return template
        elif isinstance(template, dict):
            return {k: self._render_content(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._render_content(v, context) for v in template]
        else:
            return template