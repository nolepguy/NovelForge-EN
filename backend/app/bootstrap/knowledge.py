"""Knowledge base initialization

Load knowledge base content from the file system and initialize it into the database.
"""

import os
from sqlmodel import Session, select
from loguru import logger

from app.db.models import Knowledge
from app.core.config import settings
from .registry import initializer


@initializer(name="Knowledge Base", order=30)
def init_knowledge(session: Session) -> None:
    """Initialize knowledge base

    Import *.txt and *.md files from the bootstrap/knowledge directory.

    Args:
        session: database session
    """
    knowledge_dir = os.path.join(os.path.dirname(__file__), 'knowledge')
    if not os.path.exists(knowledge_dir):
        logger.warning(f"Knowledge directory not found at {knowledge_dir}. Cannot load knowledge base.")
        return

    existing = {k.name: k for k in session.exec(select(Knowledge)).all()}
    created = 0
    updated = 0
    skipped = 0
    overwrite = settings.bootstrap.should_overwrite

    for filename in os.listdir(knowledge_dir):
        if not filename.lower().endswith(('.txt', '.md')):
            continue
        file_path = os.path.join(knowledge_dir, filename)
        name = os.path.splitext(filename)[0]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
        except Exception as e:
            logger.warning(f"Failed to read knowledge base file {file_path}: {e}")
            continue
        description = f"Built-in knowledge base: {name}"
        if name in existing:
            if overwrite:
                kb = existing[name]
                kb.content = content
                kb.description = description
                kb.built_in = True
                updated += 1
            else:
                skipped += 1
        else:
            session.add(Knowledge(name=name, description=description, content=content, built_in=True))
            created += 1

    if created or updated:
        session.commit()
        logger.info(f"Knowledge base initialized: added {created}, updated {updated} (overwrite={overwrite}, skipped {skipped})")
    else:
        logger.info(f"Knowledge base is up to date (overwrite={overwrite}, skipped {skipped}).")
