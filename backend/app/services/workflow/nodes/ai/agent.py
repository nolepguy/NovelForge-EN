"""Agent node

Provides multi-step reasoning and tool-calling capability, supporting chained
conversation history.
"""

from typing import Any, Dict, List, Optional, AsyncIterator
from pydantic import BaseModel, Field
from loguru import logger

from ...registry import register_node
from ..base import BaseNode
from app.services.ai.core.chat_model_factory import build_chat_model
from app.services.ai.core.agent_builder import build_agent
from app.services.ai.assistant.tools import (
    ASSISTANT_TOOL_REGISTRY,
    AssistantDeps,
    set_assistant_deps,
)


# ============================================================
# Input/Output Models
# ============================================================

class AgentInput(BaseModel):
    """Agent input"""
    instruction: str = Field(..., description="Task instruction")
    project_id: Optional[int] = Field(None, description="Project ID (must be passed when using project-related tools)")
    system_prompt: Optional[str] = Field(
        "You are a professional writing assistant, helping users complete novel creation tasks.",
        description="System prompt"
    )
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    llm_config_id: int = Field(..., description="LLM config ID", gt=0)
    temperature: float = Field(0.7, description="Temperature parameter", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum generated token count", gt=0)
    timeout: int = Field(60, description="Timeout (seconds)", gt=0)
    role_name: str = Field("Assistant", description="Agent role name")
    tools: List[str] = Field(
        default_factory=list,
        description="List of enabled tools",
        json_schema_extra={"x-component": "ToolMultiSelect"}
    )
    max_steps: int = Field(10, ge=1, le=50, description="Maximum reasoning steps")


class AgentOutput(BaseModel):
    """Agent output"""
    response: str = Field(..., description="Agent reply")
    new_history: List[Dict[str, Any]] = Field(..., description="Updated conversation history")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="List of created/modified cards")


# ============================================================
# Node Implementation
# ============================================================

# @register_node Not fully tested yet, temporarily unused
class AgentNode(BaseNode[AgentInput, AgentOutput]):
    """Agent node"""
    
    node_type = "AI.Agent"
    category = "ai"
    label = "AI Agent"
    description = "An agent that supports tool calling and can perform multi-step reasoning"
    
    input_model = AgentInput
    output_model = AgentOutput

    async def execute(self, input_data: AgentInput) -> AsyncIterator[AgentOutput]:
        """Execute the Agent"""
        
        # Use the explicitly passed project ID (optional)
        project_id = input_data.project_id or -1
        
        # Set AssistantDeps
        deps = AssistantDeps(
            session=self.context.session,
            project_id=project_id
        )
        set_assistant_deps(deps)
        
        # Build the ChatModel
        model = build_chat_model(
            session=self.context.session,
            llm_config_id=input_data.llm_config_id,
            temperature=input_data.temperature,
            max_tokens=input_data.max_tokens,
            timeout=input_data.timeout,
        )
        
        # Filter tools
        selected_tools = []
        for tool_name in input_data.tools:
            tool = ASSISTANT_TOOL_REGISTRY.get(tool_name)
            if tool:
                selected_tools.append(tool)
            else:
                logger.warning(f"[AI.Agent] Tool not found: {tool_name}")
        
        if not selected_tools:
            logger.warning("[AI.Agent] No tools selected, will use plain text mode")
        
        # Build the Agent
        agent = build_agent(
            model=model,
            tools=selected_tools,
            system_prompt=input_data.system_prompt,
            enable_summarization=False,
        )
        
        # Build messages
        messages = []
        
        # Add history messages
        if input_data.history:
            messages.extend(input_data.history)
        
        # Add the current instruction
        messages.append({
            "role": "user",
            "content": input_data.instruction
        })
        
        # Execute the Agent (non-streaming)
        result = await agent.ainvoke({"messages": messages})
        
        # Extract the response
        response_text = ""
        final_messages = []
        
        if isinstance(result, dict):
            result_messages = result.get("messages", [])
            if result_messages:
                # Get the last AI message
                for msg in reversed(result_messages):
                    if hasattr(msg, 'content'):
                        response_text = msg.content
                        break
                    elif isinstance(msg, dict) and msg.get("role") == "assistant":
                        response_text = msg.get("content", "")
                        break
                
                # Save the full history
                final_messages = result_messages
        
        # Convert the message format to a serializable dict
        serializable_history = []
        for msg in final_messages:
            if hasattr(msg, 'dict'):
                serializable_history.append(msg.dict())
            elif hasattr(msg, 'model_dump'):
                serializable_history.append(msg.model_dump())
            elif isinstance(msg, dict):
                serializable_history.append(msg)
            else:
                serializable_history.append({
                    "role": "assistant" if hasattr(msg, 'content') else "user",
                    "content": str(msg)
                })
        
        logger.info(
            f"[AI.Agent] Agent executed successfully: role={input_data.role_name}, "
            f"tools={len(selected_tools)}, response_length={len(response_text)}"
        )
        
        yield AgentOutput(
            response=response_text,
            new_history=serializable_history,
            artifacts=[]  # TODO: track cards created by tool calls
        )