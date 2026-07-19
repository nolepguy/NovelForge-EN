"""Workflow initialization

Load workflow definitions from the file system and initialize them into the database.
Supports .wf format code-based workflows.
"""

import os
from sqlmodel import Session, select
from loguru import logger

from app.db.models import Workflow
from app.core.config import settings
from .registry import initializer


def _parse_code_workflow(file_path: str) -> dict:
    """Parse a code-based workflow file (.wf format)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Workflow name is always derived from the filename, to avoid name drift caused by file header comments
    name = os.path.splitext(os.path.basename(file_path))[0]
    description = f"Built-in workflow: {name}"

    return {
        "name": name,
        "description": description,
        "code": code,
        "keep_run_history": False,  # Code-based workflows do not keep history by default
    }


def _create_or_update_workflow(session: Session, name: str, description: str,
                               code: str, keep_run_history: bool,
                               overwrite: bool) -> tuple[int, int, int]:
    """Create or update a single workflow (using triggers_cache)"""
    created_count = updated_count = skipped_count = 0

    wf = session.exec(select(Workflow).where(Workflow.name == name)).first()
    if not wf:
        wf = Workflow(
            name=name,
            description=description,
            is_built_in=True,
            is_active=True,
            dsl_version=2,  # Code-based workflows use version 2
            definition_code=code,
            keep_run_history=keep_run_history
        )
        session.add(wf)
        session.commit()
        session.refresh(wf)
        created_count += 1
        logger.info(f"Created built-in workflow: {name} (id={wf.id})")
    else:
        if overwrite:
            wf.definition_code = code
            wf.description = description
            wf.is_built_in = True
            wf.is_active = True
            wf.dsl_version = 2
            wf.keep_run_history = keep_run_history
            session.add(wf)
            session.commit()
            updated_count += 1
            logger.info(f"Updated built-in workflow: {name} (id={wf.id})")
        else:
            skipped_count += 1

    # Sync triggers cache
    from app.services.workflow.trigger_extractor import sync_triggers_cache
    sync_triggers_cache(wf, session)
    session.commit()

    return created_count, updated_count, skipped_count


def get_all_workflow_files() -> dict:
    """Load all workflows from the file system

    Scan for .wf format code-based workflow files

    Returns:
        workflow dict, keyed by workflow name
    """
    workflow_dir = os.path.join(os.path.dirname(__file__), 'workflows')
    if not os.path.exists(workflow_dir):
        logger.warning(f"Workflow directory not found at {workflow_dir}. Cannot load workflows.")
        return {}

    workflow_files = {}
    for filename in os.listdir(workflow_dir):
        if filename.endswith('.wf'):
            file_path = os.path.join(workflow_dir, filename)
            try:
                workflow_data = _parse_code_workflow(file_path)
                name = workflow_data["name"]
                workflow_files[name] = workflow_data
                logger.debug(f"Loaded workflow file: {filename} -> {name}")
            except Exception as e:
                logger.error(f"Failed to parse workflow file {filename}: {e}")
                import traceback
                traceback.print_exc()
                continue

    return workflow_files

@initializer(name="Workflows", order=50)
def init_workflows(session: Session) -> None:
    """Initialize built-in workflows

    Load all .wf workflow files from the bootstrap/workflows/ directory.
    Behavior is controlled by the BOOTSTRAP_OVERWRITE config.

    Args:
        session: database session
    """
    overwrite = settings.bootstrap.should_overwrite
    total_created = total_updated = total_skipped = 0

    # Load all workflow files
    all_workflows = get_all_workflow_files()

    if not all_workflows:
        logger.warning("No workflow definition files found")
        return

    # Process each workflow
    for name, workflow_data in all_workflows.items():
        try:
            c, u, s = _create_or_update_workflow(
                session,
                name=workflow_data["name"],
                description=workflow_data["description"],
                code=workflow_data["code"],
                keep_run_history=workflow_data.get("keep_run_history", False),
                overwrite=overwrite
            )
            total_created += c
            total_updated += u
            total_skipped += s
        except Exception as e:
            logger.error(f"Failed to initialize workflow {name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if total_created > 0 or total_updated > 0:
        logger.info(f"Workflow initialization complete: +{total_created}, ~{total_updated}, -{total_skipped}")
    else:
        logger.info(f"All workflows are up to date (skip={total_skipped})")
