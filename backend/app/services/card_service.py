from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Card, CardType, Project
from app.schemas.card import CardCreate, CardUpdate, CardTypeCreate, CardTypeUpdate
from app.exceptions import BusinessException
import logging
import hashlib
# Import dynamic info models
from app.schemas.entity import UpdateDynamicInfo, CharacterCard, DynamicInfoItem
from sqlalchemy import update as sa_update

logger = logging.getLogger(__name__)


def _compute_legacy_snapshot_hash(input_text: str) -> str:
    hash_value = 5381
    for char in input_text or "":
        hash_value = ((hash_value << 5) + hash_value) ^ ord(char)
    return f"h{(hash_value & 0xFFFFFFFF):x}"


def _resolve_context_template_slots(source: object, fallback: object | None = None, is_free_project: bool = False) -> dict[str, Optional[str]]:
    if is_free_project:
        return {
            "ai_context_template": None,
            "ai_context_template_review": None,
        }

    generation_template = getattr(source, "ai_context_template", None)
    review_template = getattr(source, "ai_context_template_review", None)

    if fallback is not None:
        if not generation_template:
            generation_template = getattr(fallback, "default_ai_context_template", None)
        if not review_template:
            review_template = getattr(fallback, "default_ai_context_template_review", None)

    return {
        "ai_context_template": generation_template,
        "ai_context_template_review": review_template,
    }

# Suggested upper limit for each type of dynamic info (keep the more important/newer ones when exceeded). Can be adjusted as needed.
MAX_ITEMS_BY_TYPE: dict[str, int] = {
    "Thoughts / Goal Snapshot": 3,
    "Level / Cultivation Realm": 4,
    "Techniques / Skills": 6,
    "Equipment / Treasure": 4,
    "Knowledge / Intel": 4,
    "Assets / Territory": 4,
    "Bloodline / Constitution": 4,
    # DynamicInfoType.CONNECTION: 5,
}

# Global weight threshold (default 0.45)
WEIGHT_THRESHOLD =0.45

# ---- Subtree utilities ----

def _fetch_children(db: Session, parent_ids: List[int]) -> List[Card]:
    if not parent_ids:
        return []
    stmt = select(Card).where(Card.parent_id.in_(parent_ids))
    return db.exec(stmt).all()


def _collect_subtree(db: Session, root: Card) -> List[Card]:
    """Collect the entire subtree including root via breadth-first traversal (returns in order: parents first, then children)."""
    result: List[Card] = []
    queue: List[Card] = [root]
    while queue:
        node = queue.pop(0)
        result.append(node)
        children = _fetch_children(db, [node.id])
        queue.extend(children)
    return result


def _next_display_order(db: Session, project_id: int, parent_id: Optional[int]) -> int:
    stmt = select(Card).where(Card.project_id == project_id, Card.parent_id == parent_id)
    siblings = db.exec(stmt).all()
    return len(siblings)


def _shallow_clone(src: Card, project_id: int, parent_id: Optional[int], display_order: int) -> Card:
    return Card(
        title=src.title,
        model_name=src.model_name,
        content=dict(src.content or {}),
        parent_id=parent_id,
        card_type_id=src.card_type_id,
        json_schema=dict(src.json_schema or {}) if src.json_schema is not None else None,
        ai_params=dict(src.ai_params or {}) if src.ai_params is not None else None,
        project_id=project_id,
        display_order=display_order,
        ai_context_template=src.ai_context_template,
        ai_context_template_review=src.ai_context_template_review,
    )

# ---- Title suffix generation ----

def _generate_non_conflicting_title(db: Session, project_id: int, base_title: str, card_type_id: Optional[int] = None) -> str:
    """Generate a non-conflicting title
    
    Args:
        db: Database session
        project_id: Project ID
        base_title: Base title
        card_type_id: Card type ID (if provided, only check title conflicts within the same card type)
    """
    title = (base_title or '').strip() or 'New Card'
    
    # Build query: titles within the same project
    stmt = select(Card.title).where(Card.project_id == project_id)
    
    # If a card type is specified, only check title conflicts within the same type
    if card_type_id is not None:
        stmt = stmt.where(Card.card_type_id == card_type_id)
    
    titles = db.exec(stmt).all() or []
    existing_titles = set(titles)
    
    if title not in existing_titles:
        return title
    
    # Find the maximum suffix
    import re
    pattern = re.compile(rf"^{re.escape(title)}\((\d+)\)$")
    max_n = 0
    for t in existing_titles:
        m = pattern.match(str(t))
        if m:
            try:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
            except Exception:
                continue
    return f"{title}({max_n + 1})"


class CardService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_for_project(self, project_id: int) -> List[Card]:
        # Get all cards for this project; the tree structure will be built on the client side.
        statement = (
            select(Card)
            .where(Card.project_id == project_id)
            .order_by(Card.display_order)
        )
        cards = self.db.exec(statement).all()
        return cards

    def search(self, project_id: int, query: str) -> List[Card]:
        """Search cards in a project by title or content."""
        import sqlalchemy as sa
        statement = select(Card).where(
            Card.project_id == project_id,
            sa.or_(
                Card.title.contains(query),
                sa.cast(Card.content, sa.String).contains(query)
            )
        )
        return self.db.exec(statement).all()

    def get_by_id(self, card_id: int) -> Optional[Card]:
        return self.db.get(Card, card_id)

    def create(self, card_create: CardCreate, project_id: int) -> Card:

        card_type = self.db.get(CardType, card_create.card_type_id)
        if not card_type:
             raise BusinessException(f"CardType with id {card_create.card_type_id} not found", status_code=404)

        # Singleton restriction: allowed in the reserved project (__free__)
        proj = self.db.get(Project, project_id)
        is_free_project = getattr(proj, 'name', None) == "__free__"
        if card_type.is_singleton and not is_free_project:
            statement = select(Card).where(Card.project_id == project_id, Card.card_type_id == card_create.card_type_id)
            existing_card = self.db.exec(statement).first()
            if existing_card:
                raise BusinessException(
                    f"A card of type '{card_type.name}' already exists in this project, and it is a singleton.",
                    status_code=409
                )

        # Determine display order
        statement = select(Card).where(Card.project_id == project_id, Card.parent_id == card_create.parent_id)
        sibling_cards = self.db.exec(statement).all()
        display_order = len(sibling_cards)

        context_template_slots = _resolve_context_template_slots(card_create, card_type, is_free_project=is_free_project)

        # Auto-handle title conflicts: append (n) to titles of the same card type
        final_title = _generate_non_conflicting_title(
            self.db, 
            project_id, 
            getattr(card_create, 'title', '') or card_type.name,
            card_type_id=card_create.card_type_id  # Only check cards of the same type
        )

        # Merge params: context_template_slots will override same-named fields in card_create
        card_params = {
            **card_create.model_dump(),
            'title': final_title,
            'project_id': project_id,
            'display_order': display_order,
            **context_template_slots,
        }
        
        card = Card(**card_params)
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    @staticmethod
    def create_initial_cards_for_project(db: Session, project_id: int, template_items: Optional[List[dict]] = None):
        """
        # Create the initial set of cards for a new project.
        # If template_items is provided, use them; otherwise fall back to the built-in default list (backward compatible).
        # template_items: List[ { card_type_id: int, display_order: int, title_override?: str } ]
        """
        if template_items is None:
            initial_cards_setup = {
                "Work Tags": {"order": 0},
                "Special Ability": {"order": 1},
                "One Sentence Summary": {"order": 2},
                "Story Outline": {"order": 3},
                "Worldview Setting": {"order": 4},
                "Core Blueprint": {"order": 5},
            }

            for card_type_name, setup in initial_cards_setup.items():
                try:
                    statement = select(CardType).where(CardType.name == card_type_name)
                    card_type = db.exec(statement).first()
                    if card_type:
                        # Create the card
                        new_card = Card(
                            title=card_type_name,
                            content={},
                            project_id=project_id,
                        card_type_id=card_type.id,
                            display_order=setup["order"],
                            ai_context_template=card_type.default_ai_context_template,
                            ai_context_template_review=card_type.default_ai_context_template_review,
                        )
                    db.add(new_card)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed creating initial card for type {card_type_name}: {e}")
            return

        # Create using template items
        for item in sorted(template_items, key=lambda x: x.get('display_order', 0)):
            try:
                ct = db.get(CardType, item['card_type_id'])
                if not ct:
                    continue
                title = item.get('title_override') or ct.name
                new_card = Card(
                    title=title,
                    content={},
                    project_id=project_id,
                    card_type_id=ct.id,
                    display_order=item.get('display_order', 0),
                    ai_context_template=ct.default_ai_context_template,
                    ai_context_template_review=ct.default_ai_context_template_review,
                )
                db.add(new_card)
                db.commit()
            except Exception as e:
                logger.error(f"Failed creating initial card by template item {item}: {e}")
        return

    def update(self, card_id: int, card_update: CardUpdate) -> Optional[Card]:
        card = self.get_by_id(card_id)
        if not card:
            return None
            
        update_data = card_update.model_dump(exclude_unset=True)

        # If parent_id changed, we need to update display_order
        if 'parent_id' in update_data and card.parent_id != update_data['parent_id']:
            # This logic can be complex. For now, just append to the end of the new list.
            statement = select(Card).where(Card.project_id == card.project_id, Card.parent_id == update_data['parent_id'])
            sibling_cards = self.db.exec(statement).all()
            update_data['display_order'] = len(sibling_cards)


        for key, value in update_data.items():
            setattr(card, key, value)
            
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def delete(self, card_id: int) -> bool:
        # Recursive deletion is handled by the cascade option in the relationship
        card = self.get_by_id(card_id)
        if not card:
            return False
        self.db.delete(card)
        self.db.commit()
        return True 

    def replace_field_text(self, card_id: int, field_path: str, old_text: str, new_text: str, fuzzy_match: bool = True) -> Dict[str, Any]:
        """
        Replace specified text fragments in a card field
        
        Args:
            card_id: Target card ID
            field_path: Field path (e.g. "content", "overview")
            old_text: The original text fragment to be replaced
            new_text: The new text content
            fuzzy_match: Whether to enable fuzzy matching (supports "start...end" format)
            
        Returns:
            result dict including success, replaced_count, etc.
        """
        import copy
        
        # 1. Get the card
        card = self.get_by_id(card_id)
        if not card:
            return {"success": False, "error": f"Card {card_id} does not exist"}
            
        # 2. Normalize path (auto-handle content. prefix)
        normalized_path = field_path
        if not normalized_path.startswith("content."):
            normalized_path = f"content.{normalized_path}"
            
        # 3. Get current value
        try:
            current_value = card.content or {}
            # Traverse level by level
            parts = normalized_path.split(".")[1:] # Skip content
            for part in parts:
                if isinstance(current_value, dict):
                    current_value = current_value.get(part, "")
                else:
                    return {"success": False, "error": f"Field path {normalized_path} is invalid: cannot traverse to {part}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get field value: {str(e)}"}
            
        if not isinstance(current_value, str):
            return {"success": False, "error": f"Field {field_path} is not a text type"}
            
        # 4. Matching logic
        actual_old_text = old_text
        if fuzzy_match and ("..." in old_text or "……" in old_text):
            separator = "..." if "..." in old_text else "……"
            split_parts = old_text.split(separator, 1)
            if len(split_parts) == 2:
                start_text = split_parts[0].strip()
                end_text = split_parts[1].strip()
                
                # Search range
                start_idx = current_value.find(start_text)
                if start_idx == -1:
                    return {"success": False, "error": "Start text not found", "hint": f"Start: {start_text[:20]}..."}
                
                end_search_start = start_idx + len(start_text)
                end_idx = current_value.find(end_text, end_search_start)
                if end_idx == -1:
                    return {"success": False, "error": "End text not found", "hint": f"End: ...{end_text[-20:]}"}
                
                actual_old_text = current_value[start_idx:end_idx + len(end_text)]
            else:
                 return {"success": False, "error": "Fuzzy match format error"}
        
        if actual_old_text not in current_value:
             return {"success": False, "error": "Specified original text fragment not found"}
             
        # 5. Perform replacement
        replaced_count = current_value.count(actual_old_text)
        updated_value = current_value.replace(actual_old_text, new_text)
        
        # 6. Update and save
        new_content = copy.deepcopy(card.content or {})
        target = new_content
        # Navigate to parent
        parts = normalized_path.split(".")[1:]
        for part in parts[:-1]:
            if part not in target:
                 target[part] = {}
            target = target[part]
        
        target[parts[-1]] = updated_value
        
        card.content = new_content
        flag_modified(card, "content")
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        
        return {
            "success": True,
            "card_id": card.id,
            "card_title": card.title,
            "replaced_count": replaced_count,
            "old_length": len(current_value),
            "new_length": len(updated_value)
        }

    # ---- Move and copy ----
    def replace_field_text_by_lines(
        self,
        card_id: int,
        field_path: str,
        start_line: int,
        end_line: int,
        new_text: str,
        expected_excerpt: Optional[str] = None,
        snapshot_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Replace text field fragments by line numbers (positional replacement).
        """
        import copy

        card = self.get_by_id(card_id)
        if not card:
            return {"success": False, "error": f"Card {card_id} does not exist"}

        normalized_path = field_path
        if not normalized_path.startswith("content."):
            normalized_path = f"content.{normalized_path}"

        try:
            current_value = card.content or {}
            parts = normalized_path.split(".")[1:]
            for part in parts:
                if isinstance(current_value, dict):
                    current_value = current_value.get(part, "")
                else:
                    return {"success": False, "error": f"Field path {normalized_path} is invalid: cannot traverse to {part}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get field value: {str(e)}"}

        if not isinstance(current_value, str):
            return {"success": False, "error": f"Field {field_path} is not a text type"}

        if start_line < 1 or end_line < start_line:
            return {"success": False, "error": "Invalid line number range"}

        line_sep = "\r\n" if "\r\n" in current_value else "\n"
        lines = current_value.splitlines()
        if not lines:
            lines = [""]

        total_lines = len(lines)
        if end_line > total_lines:
            return {"success": False, "error": f"Line numbers out of range: currently {total_lines} lines total"}

        start_index = start_line - 1
        end_index = end_line
        current_excerpt = line_sep.join(lines[start_index:end_index])
        excerpt_hash = hashlib.sha256(current_excerpt.encode("utf-8")).hexdigest()
        full_hash = hashlib.sha256(current_value.encode("utf-8")).hexdigest()
        legacy_excerpt_hash = _compute_legacy_snapshot_hash(current_excerpt)
        legacy_full_hash = _compute_legacy_snapshot_hash(current_value)
        if snapshot_hash and snapshot_hash not in {
            excerpt_hash,
            full_hash,
            legacy_excerpt_hash,
            legacy_full_hash,
        }:
            return {
                "success": False,
                "error": "Snapshot verification failed, content may have changed",
                "expected_snapshot_hash": snapshot_hash,
                "actual_excerpt_hash": excerpt_hash,
                "actual_full_hash": full_hash,
                "actual_legacy_excerpt_hash": legacy_excerpt_hash,
                "actual_legacy_full_hash": legacy_full_hash,
            }

        if expected_excerpt is not None and expected_excerpt.strip() and expected_excerpt.strip() != current_excerpt.strip():
            return {
                "success": False,
                "error": "Original fragment verification failed, content may have changed",
                "expected_excerpt": expected_excerpt,
                "actual_excerpt": current_excerpt,
            }

        new_lines = new_text.splitlines()
        updated_lines = lines[:start_index] + new_lines + lines[end_index:]
        updated_value = line_sep.join(updated_lines)
        if current_value.endswith("\r\n"):
            updated_value = f"{updated_value}\r\n"
        elif current_value.endswith("\n"):
            updated_value = f"{updated_value}\n"

        new_content = copy.deepcopy(card.content or {})
        target = new_content
        path_parts = normalized_path.split(".")[1:]
        for part in path_parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[path_parts[-1]] = updated_value

        card.content = new_content
        flag_modified(card, "content")
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)

        return {
            "success": True,
            "card_id": card.id,
            "card_title": card.title,
            "field_path": field_path,
            "start_line": start_line,
            "end_line": end_line,
            "replaced_line_count": end_line - start_line + 1,
            "new_line_count": len(new_lines),
            "line_delta": len(new_lines) - (end_line - start_line + 1),
            "snapshot_hash": excerpt_hash,
        }

    def move_card(self, card_id: int, target_project_id: int, parent_id: Optional[int] = None) -> Optional[Card]:
        root = self.get_by_id(card_id)
        if not root:
            return None
        # Collect subtree
        subtree = _collect_subtree(self.db, root)
        id_set = {c.id for c in subtree}
        # Validate: if parent_id is specified, cannot set parent to another node inside the subtree (avoid cycles)
        if parent_id and parent_id in id_set and parent_id != root.id:
            raise BusinessException("Cannot set parent to a descendant of itself", status_code=400)
        # Target parent project validation
        if parent_id is not None:
            parent_card = self.get_by_id(parent_id)
            if not parent_card:
                raise BusinessException("Target parent card not found", status_code=404)
            if parent_card.project_id != target_project_id:
                raise BusinessException("Target parent card not in target project", status_code=400)
        # Singleton restriction for non-reserved projects (validated during cross-project move)
        if target_project_id != root.project_id:
            target_proj = self.db.get(Project, target_project_id)
            is_target_free = getattr(target_proj, 'name', None) == "__free__"
            if root.card_type and getattr(root.card_type, 'is_singleton', False) and not is_target_free:
                exists_stmt = select(Card).where(Card.project_id == target_project_id, Card.card_type_id == root.card_type_id)
                exists = self.db.exec(exists_stmt).first()
                if exists:
                    raise BusinessException(f"A card of type '{root.card_type.name}' already exists in target project (singleton)", status_code=409)
        # Update project ID (entire subtree)
        for node in subtree:
            node.project_id = target_project_id
        # Adjust root's parent and display order
        root.parent_id = parent_id
        # Singleton restriction: multiple cards of the same type are allowed in the reserved project (__free__), so display_order can also be appended directly
        root.display_order = _next_display_order(self.db, target_project_id, parent_id)
        # Commit
        for node in subtree:
            self.db.add(node)
        self.db.commit()
        self.db.refresh(root)
        return root

    def copy_card(self, card_id: int, target_project_id: int, parent_id: Optional[int] = None) -> Optional[Card]:
        src_root = self.get_by_id(card_id)
        if not src_root:
            return None
        # Singleton restriction for non-reserved projects (validate root type when copying to target)
        target_proj = self.db.get(Project, target_project_id)
        is_target_free = getattr(target_proj, 'name', None) == "__free__"
        if src_root.card_type and getattr(src_root.card_type, 'is_singleton', False) and not is_target_free:
            exists_stmt = select(Card).where(Card.project_id == target_project_id, Card.card_type_id == src_root.card_type_id)
            exists = self.db.exec(exists_stmt).first()
            if exists:
                raise BusinessException(f"A card of type '{src_root.card_type.name}' already exists in target project (singleton)", status_code=409)
        # Collect subtree and copy in parent-first order
        subtree = _collect_subtree(self.db, src_root)
        old_to_new_id: dict[int, int] = {}
        new_nodes_by_old_id: dict[int, Card] = {}
        for node in subtree:
            # Compute new parent ID
            if node.id == src_root.id:
                new_parent_id = parent_id
                new_order = _next_display_order(self.db, target_project_id, new_parent_id)
            else:
                old_parent_id = node.parent_id
                new_parent_id = old_to_new_id.get(old_parent_id) if old_parent_id is not None else None
                new_order = _next_display_order(self.db, target_project_id, new_parent_id)
            clone = _shallow_clone(node, target_project_id, new_parent_id, new_order)
            # Also avoid title conflicts when copying
            clone.title = _generate_non_conflicting_title(self.db, target_project_id, clone.title)
            self.db.add(clone)
            self.db.commit()
            self.db.refresh(clone)
            old_to_new_id[node.id] = clone.id
            new_nodes_by_old_id[node.id] = clone
        return new_nodes_by_old_id.get(src_root.id)


class CardTypeService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[CardType]:
        return self.db.exec(select(CardType)).all()

    def get_by_id(self, card_type_id: int) -> Optional[CardType]:
        return self.db.get(CardType, card_type_id)
        
    def create(self, card_type_create: CardTypeCreate) -> CardType:
        card_type = CardType.model_validate(card_type_create)
        self.db.add(card_type)
        self.db.commit()
        self.db.refresh(card_type)
        return card_type

    def update(self, card_type_id: int, card_type_update: CardTypeUpdate) -> Optional[CardType]:
        card_type = self.get_by_id(card_type_id)
        if not card_type:
            return None
        for key, value in card_type_update.model_dump(exclude_unset=True).items():
            setattr(card_type, key, value)
        self.db.add(card_type)
        self.db.commit()
        self.db.refresh(card_type)
        return card_type

    def delete(self, card_type_id: int) -> bool:
        card_type = self.get_by_id(card_type_id)
        if not card_type:
            return False
        # Consider cascading deletes or checks for associated cards
        self.db.delete(card_type)
        self.db.commit()
        return True 
