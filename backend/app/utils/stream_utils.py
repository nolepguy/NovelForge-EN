"""Streaming response utility functions"""

import json
from typing import AsyncGenerator


async def wrap_sse_stream(generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """Wrap a plain text stream into SSE (Server-Sent Events) format
    
    Args:
        generator: Async text generator
        
    Yields:
        A data stream in SSE format
    """
    async for item in generator:
        yield f"data: {json.dumps({'content': item}, ensure_ascii=False)}\n\n"
