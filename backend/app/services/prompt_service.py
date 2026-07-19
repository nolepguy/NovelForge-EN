from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from app.db.models import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate
from string import Template
import re

def get_prompt(session: Session, prompt_id: int) -> Optional[Prompt]:
    """Get a single prompt by ID"""
    return session.get(Prompt, prompt_id)

def get_prompt_by_name(session: Session, prompt_name: str) -> Optional[Prompt]:
    """Get a single prompt by name"""
    statement = select(Prompt).where(Prompt.name == prompt_name)
    return session.exec(statement).first()

def get_prompts(session: Session, skip: int = 0, limit: int = 100) -> List[Prompt]:
    """Get the prompt list"""
    statement = select(Prompt).offset(skip).limit(limit)
    return session.exec(statement).all()

def create_prompt(session: Session, prompt_create: PromptCreate) -> Prompt:
    """Create a new prompt"""
    # Check if the name already exists
    existing_prompt = get_prompt_by_name(session, prompt_create.name)
    if existing_prompt:
        raise ValueError(f"Prompt name '{prompt_create.name}' already exists")
    
    db_prompt = Prompt.model_validate(prompt_create)
    session.add(db_prompt)
    session.commit()
    session.refresh(db_prompt)
    return db_prompt

def update_prompt(session: Session, prompt_id: int, prompt_update: PromptUpdate) -> Optional[Prompt]:
    """Update a prompt"""
    db_prompt = session.get(Prompt, prompt_id)
    if not db_prompt:
        return None
    prompt_data = prompt_update.model_dump(exclude_unset=True)
    for key, value in prompt_data.items():
        setattr(db_prompt, key, value)
    session.add(db_prompt)
    session.commit()
    session.refresh(db_prompt)
    return db_prompt

def delete_prompt(session: Session, prompt_id: int) -> bool:
    """Delete a prompt"""
    db_prompt = session.get(Prompt, prompt_id)
    if not db_prompt:
        return False
    session.delete(db_prompt)
    session.commit()
    return True

def render_prompt(prompt_template: str, context: Dict[str, Any]) -> str:
    """
    Render the prompt template using the context.
    
    :param prompt_template: String template with placeholders (e.g., "Hello, ${name}")
    :param context: Dict containing values to fill into the template (e.g., {"name": "world"})
    :return: The rendered string ("Hello, world")
    """
    template = Template(prompt_template)
    try:
        return template.substitute(context)
    except KeyError as e:
        raise ValueError(f"Failed to render prompt: missing variable in context '{e.args[0]}'")
    except Exception as e:
        raise ValueError(f"Unknown error occurred while rendering prompt: {e}")


# Knowledge base placeholder resolution
_KB_ID_PATTERN = re.compile(r"@KB\{\s*id\s*=\s*(\d+)\s*\}")
_KB_NAME_PATTERN = re.compile(r"@KB\{\s*name\s*=\s*([^}]+)\}")


def inject_knowledge(session: Session, template: str) -> str:
    """Inject knowledge base placeholders in the template with actual content
    
    Rules:
    1) For multiple placeholders within a "- knowledge:" section, inject them in order and separate with numbering:
       - knowledge:\n1.\n<KB1>\n\n2.\n<KB2> ...
    2) If placeholders appear outside the knowledge section, replace them in-place with the full knowledge text.
    3) If the corresponding knowledge base is not found, keep a comment placeholder to avoid interruption.
    
    Args:
        session: Database session
        template: Prompt template
        
    Returns:
        The template with knowledge bases injected
    """
    from app.services.knowledge_service import KnowledgeService
    
    svc = KnowledgeService(session)

    def fetch_kb_by_id(kid: int) -> str:
        kb = svc.get_by_id(kid)
        return kb.content if kb and kb.content else f"/* Knowledge base not found: id={kid} */"

    def fetch_kb_by_name(name: str) -> str:
        kb = svc.get_by_name(name)
        return kb.content if kb and kb.content else f"/* Knowledge base not found: name={name} */"

    # First process the knowledge sections (more structured injection)
    lines = template.splitlines()
    i = 0
    out_lines: list[str] = []
    while i < len(lines):
        line = lines[i]
        # Match top-level "- knowledge:" lines (case-insensitive)
        if re.match(r"^\s*-\s*knowledge\s*:\s*$", line, flags=re.IGNORECASE):
            # Collect placeholder lines within this section until the next top-level "- <Something>" line or end of file
            j = i + 1
            block_lines: list[str] = []
            while j < len(lines) and not re.match(r"^\s*-\s*\w", lines[j]):
                block_lines.append(lines[j])
                j += 1
            # Extract placeholder order
            placeholders: list[tuple[str, str]] = []  # (mode, value)
            for bl in block_lines:
                for m in _KB_ID_PATTERN.finditer(bl):
                    placeholders.append(("id", m.group(1)))
                for m in _KB_NAME_PATTERN.finditer(bl):
                    placeholders.append(("name", m.group(1).strip().strip('\"\'')))
            # Build numbered content
            out_lines.append(line)  # Keep the title line "- knowledge:"
            if placeholders:
                for idx, (mode, val) in enumerate(placeholders, start=1):
                    out_lines.append(f"{idx}.")
                    if mode == "id":
                        try:
                            content = fetch_kb_by_id(int(val))
                        except Exception:
                            content = f"/* Knowledge base not found: id={val} */"
                    else:
                        content = fetch_kb_by_name(val)
                    out_lines.append(content.strip())
                    # Blank line between sections
                    if idx < len(placeholders):
                        out_lines.append("")
            # Skip the original block
            i = j
            continue
        else:
            out_lines.append(line)
            i += 1

    enumerated_text = "\n".join(out_lines)

    # In-place replacement outside knowledge sections (if placeholders remain)
    def repl_id(m: re.Match) -> str:
        try:
            kid = int(m.group(1))
        except Exception:
            return f"/* Knowledge base not found: id={m.group(1)} */"
        return fetch_kb_by_id(kid)

    def repl_name(m: re.Match) -> str:
        name = m.group(1).strip().strip('\"\'')
        return fetch_kb_by_name(name)

    result = _KB_ID_PATTERN.sub(repl_id, enumerated_text)
    result = _KB_NAME_PATTERN.sub(repl_name, result)
    return result 