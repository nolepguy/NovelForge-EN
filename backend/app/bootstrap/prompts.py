"""Prompt initialization

Load prompt templates from the file system and initialize them into the database.
"""

import os
from sqlmodel import Session, select
from loguru import logger

from app.db.models import Prompt
from app.core.config import settings
from .registry import initializer


def _parse_prompt_file(file_path: str) -> dict:
    """Parse a single prompt file

    Args:
        file_path: prompt file path

    Returns:
        dict containing name, description, template
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    name = os.path.splitext(filename)[0]
    description = f"AI task prompt: {name}"

    return {
        "name": name,
        "description": description,
        "template": content.strip()
    }


def get_all_prompt_files() -> dict:
    """Load all prompts from the file system

    Returns:
        prompt dict, keyed by prompt name
    """
    prompt_dir = os.path.join(os.path.dirname(__file__), 'prompts')
    if not os.path.exists(prompt_dir):
        logger.warning(f"Prompt directory not found at {prompt_dir}. Cannot load prompts.")
        return {}

    prompt_files = {}
    for filename in os.listdir(prompt_dir):
        if filename.endswith(('.prompt', '.txt')):
            file_path = os.path.join(prompt_dir, filename)
            name = os.path.splitext(filename)[0]
            prompt_files[name] = _parse_prompt_file(file_path)
    return prompt_files


@initializer(name="Prompts", order=10)
def init_prompts(session: Session) -> None:
    """Initialize default prompts

    Behavior is controlled by the BOOTSTRAP_OVERWRITE config:
    - True: overwrite and update existing prompts
    - False: skip existing prompts

    Args:
        session: database session
    """
    overwrite = settings.bootstrap.should_overwrite
    existing_prompts = session.exec(select(Prompt)).all()
    existing_names = {p.name for p in existing_prompts}

    all_prompts_data = get_all_prompt_files()

    new_count = 0
    updated_count = 0
    skipped_count = 0
    prompts_to_add = []

    for name, prompt_data in all_prompts_data.items():
        if name in existing_names:
            if overwrite:
                existing_prompt = next(p for p in existing_prompts if p.name == name)
                existing_prompt.template = prompt_data['template']
                existing_prompt.description = prompt_data.get('description')
                existing_prompt.built_in = True
                updated_count += 1
            else:
                skipped_count += 1
        else:
            prompts_to_add.append(Prompt(**prompt_data, built_in=True))
            new_count += 1

    if prompts_to_add:
        session.add_all(prompts_to_add)

    if new_count > 0 or updated_count > 0:
        session.commit()
        logger.info(f"Prompts updated: added {new_count}, updated {updated_count} (overwrite={overwrite}, skipped {skipped_count}).")
    else:
        logger.info(f"All prompts are up to date (overwrite={overwrite}, skipped {skipped_count}).")
