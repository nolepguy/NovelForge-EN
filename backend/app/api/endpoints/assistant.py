"""
Inspiration assistant endpoints.
Supports tool-calling conversations.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncGenerator
from loguru import logger

from app.db.session import get_session
from app.services.ai.assistant.assistant_service import generate_assistant_chat_streaming
from app.schemas.ai import AssistantChatRequest
from app.utils.stream_utils import wrap_sse_stream

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(
    request: AssistantChatRequest,
    session: Session = Depends(get_session)
):
    """
    Inspiration assistant chat endpoint (supports tool calling).
    
    Features:
    - Dedicated request model (clear semantics)
    - Auto-injected tool set
    - Supports streaming output
    - Supports returning tool-call results
    """
    # Load the system prompt (select different prompts based on mode)
    from app.services import prompt_service
    
    prompt_name = request.prompt_name
    react_enabled = bool(getattr(request, "react_mode_enabled", False))

    if react_enabled:
        react_prompt_name = f"{prompt_name}-React"
        p = prompt_service.get_prompt_by_name(session, react_prompt_name)
        if p and p.template:
            system_prompt = str(p.template)
            logger.info(f"[Assistant API] React mode enabled, using prompt {react_prompt_name}")
        else:
            logger.warning(f"[Assistant API] React mode enabled but {react_prompt_name} not found, falling back to standard prompt {prompt_name}")
            p = prompt_service.get_prompt_by_name(session, prompt_name)
            if not p or not p.template:
                raise HTTPException(status_code=400, detail=f"Prompt not found: {prompt_name}")
            system_prompt = str(p.template)
    else:
        p = prompt_service.get_prompt_by_name(session, prompt_name)
        if not p or not p.template:
            raise HTTPException(status_code=400, detail=f"Prompt not found: {prompt_name}")
        system_prompt = str(p.template)
    
    # All modes uniformly use the LangChain ChatModel + Tools pipeline
    async def stream_with_tools() -> AsyncGenerator[str, None]:
        logger.info("[Assistant API] Using {} mode".format("React" if react_enabled else "standard"))
        async for chunk in generate_assistant_chat_streaming(
            session=session,
            request=request,
            system_prompt=system_prompt,
            track_stats=True,
        ):
            yield chunk
    
    return StreamingResponse(
        wrap_sse_stream(stream_with_tools()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
