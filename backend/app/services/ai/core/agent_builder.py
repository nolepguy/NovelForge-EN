"""Agent builder

Extracts agent creation logic for reuse by the inspiration assistant and workflow nodes.
"""

from typing import List, Optional
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from loguru import logger


def build_agent(
    model: BaseChatModel,
    tools: List[BaseTool],
    system_prompt: str,
    enable_summarization: bool = False,
    max_tokens_before_summary: int = 8192,
):
    """Build a LangChain Agent

    Args:
        model: LangChain ChatModel instance
        tools: List of tools
        system_prompt: System prompt
        enable_summarization: Whether to enable context summarization
        max_tokens_before_summary: Token threshold that triggers summarization

    Returns:
        A LangChain Agent instance
    """
    middleware = []

    if enable_summarization:
        try:
            middleware.append(
                SummarizationMiddleware(
                    model=model,
                    max_tokens_before_summary=max_tokens_before_summary,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to initialize SummarizationMiddleware, context summarization will be ignored: {e}")

    # Use LangChain 1.x create_agent to build a tool-enabled agent
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
    )

    return agent