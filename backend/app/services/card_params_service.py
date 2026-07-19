"""Card params service

Handles merging, validation, and other business logic for card AI parameters.
"""

from typing import Dict, Any
from sqlmodel import Session
from app.db.models import Card, LLMConfig
from loguru import logger


def merge_effective_ai_params(session: Session, card: Card) -> Dict[str, Any]:
    """Merge the effective AI parameters for a card
    
    Merge logic:
    1. Base params come from CardType.ai_params
    2. Override params come from Card.ai_params
    3. Fill in missing llm_config_id (select the LLM with the smallest ID)
    4. Normalize types
    
    Args:
        session: Database session
        card: Card object
        
    Returns:
        The merged effective params dict
    """
    # Get base params (from type)
    base = (card.card_type.ai_params if card.card_type and card.card_type.ai_params else {}) or {}
    
    # Get override params (from instance)
    override = (card.ai_params or {})
    
    # Merge params
    effective = {**base, **override}
    
    # Fill in llm_config_id (if missing)
    if effective.get("llm_config_id") in (None, 0, "0", ""):
        try:
            # Use the LLM with the smallest ID as the default
            llm = session.query(LLMConfig).order_by(LLMConfig.id.asc()).first()  # type: ignore
            if llm:
                effective["llm_config_id"] = int(getattr(llm, "id", 0))
        except Exception as e:
            logger.warning(f"Failed to get default LLM config: {e}")
    
    # Normalize llm_config_id type
    if effective.get("llm_config_id") is not None:
        try:
            effective["llm_config_id"] = int(effective.get("llm_config_id"))
        except (ValueError, TypeError):
            pass
    
    return effective
