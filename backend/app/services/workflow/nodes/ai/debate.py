"""Multi-agent debate node

Implements multi-round debate via two differently configured agents within a single node.
Supports CoT (Chain of Thought); Thought content is mutually invisible.
Supports progress reporting and checkpoint recovery.
"""

from typing import Any, Dict, List, Optional, AsyncIterator, TYPE_CHECKING
from pydantic import BaseModel, Field
from loguru import logger

if TYPE_CHECKING:
    from ...engine.async_executor import ProgressEvent

from ...registry import register_node
from ..base import BaseNode
from app.services.ai.core.llm_service import generate_structured


# ============================================================
# Helper Models
# ============================================================

class DebateMessage(BaseModel):
    """Debate message structure (CoT enforced)"""
    thought: str = Field(..., description="Inner thought process, tactical analysis (invisible to the opponent)")
    content: str = Field(..., description="Public speech content (visible to the opponent)")


# ============================================================
# Input/Output Models
# ============================================================

class DebateInput(BaseModel):
    """Debate node input"""
    topic: str = Field(..., description="Debate topic")
    context: Optional[str] = Field(None, description="Background material/context")
    max_rounds: int = Field(3, description="Maximum debate rounds (A->B is one round)", ge=1, le=20)
    
    # Agent 1 config
    agent_1_name: str = Field("Pro", description="Role 1 name")
    agent_1_system_prompt: str = Field("", description="Role 1 persona prompt", json_schema_extra={"x-component": "Textarea"})
    agent_1_llm_config: int = Field(..., description="Role 1 LLM config", json_schema_extra={"x-component": "LLMSelect"})
    
    # Agent 2 config
    agent_2_name: str = Field("Con", description="Role 2 name")
    agent_2_system_prompt: str = Field("", description="Role 2 persona prompt", json_schema_extra={"x-component": "Textarea"})
    agent_2_llm_config: int = Field(..., description="Role 2 LLM config", json_schema_extra={"x-component": "LLMSelect"})
    
    temperature: float = Field(0.7, description="Generation temperature", ge=0.0, le=2.0)
    max_tokens: int = Field(2000, description="Maximum tokens per reply")


class DebateOutput(BaseModel):
    """Debate node output"""
    summary: str = Field(..., description="Debate summary / final speech")
    history: List[Dict[str, Any]] = Field(..., description="Public conversation history (excluding thoughts), format [{'role': 'Pro'/'Con', 'content': 'speech content'}, ...]; formatting is recommended if displayed")
    full_log: List[Dict[str, Any]] = Field(..., description="Full log (including thoughts)")
    total_rounds: int = Field(..., description="Actual number of completed debate rounds")


# ============================================================
# Node Implementation
# ============================================================

@register_node
class DebateNode(BaseNode[DebateInput, DebateOutput]):
    """Multi-agent debate node"""
    
    node_type = "AI.Debate"
    category = "ai"
    label = "Multi-Agent Debate"
    description = "Two agents debate a specific topic over multiple rounds (supports CoT, progress reporting, checkpoint recovery)"
    
    input_model = DebateInput
    output_model = DebateOutput

    async def execute(self, input_data: DebateInput) -> AsyncIterator:
        """Execute the debate loop (serial processing, supports checkpoint recovery)"""
        from ...engine.async_executor import ProgressEvent
        
        # 1. Checkpoint recovery
        checkpoint = getattr(self.context, 'checkpoint', None)
        completed_rounds = checkpoint.get('completed_rounds', 0) if checkpoint else 0
        history_public = checkpoint.get('history_public', []) if checkpoint else []
        full_log = checkpoint.get('full_log', []) if checkpoint else []
        
        # Recover the conversation context (simplified: only save message content)
        agent_1_context = checkpoint.get('agent_1_context', []) if checkpoint else []
        agent_2_context = checkpoint.get('agent_2_context', []) if checkpoint else []
        
        # Initialize (first time only)
        if completed_rounds == 0:
            user_input = f"Debate topic: {input_data.topic}"
            if input_data.context:
                user_input += f"\n\nBackground material:\n{input_data.context}"
                
            logger.info(f"[AI.Debate] Starting debate: {input_data.agent_1_name} vs {input_data.agent_2_name}, topic={input_data.topic}")

            # Initialize the context (only save strings)
            agent_1_context = [user_input]
            agent_2_context = [user_input]
        else:
            logger.info(f"[AI.Debate] Resumed from checkpoint: completed {completed_rounds}/{input_data.max_rounds} rounds")
        
        # 2. Debate loop (serial processing)
        for round_idx in range(completed_rounds, input_data.max_rounds):
            try:
                # === Agent 1 speaks ===
                logger.info(f"[AI.Debate] Round {round_idx + 1} - {input_data.agent_1_name} is speaking...")
                
                msg_1 = await self._agent_turn(
                    name=input_data.agent_1_name,
                    llm_config_id=input_data.agent_1_llm_config,
                    system_prompt=input_data.agent_1_system_prompt,
                    context=agent_1_context,
                    input_data=input_data,
                    role="Agent 1"
                )
                
                # Update records
                content_1 = msg_1.content
                thought_1 = msg_1.thought
                
                log_entry_1 = {
                    "round": round_idx + 1,
                    "role": input_data.agent_1_name,
                    "type": "Agent 1",
                    "thought": thought_1,
                    "content": content_1
                }
                full_log.append(log_entry_1)
                history_public.append({"role": input_data.agent_1_name, "content": content_1})
                
                # Update the context (simplified: only save content strings)
                agent_2_context.append(f"[{input_data.agent_1_name}]: {content_1}")
                agent_1_context.append(f"[My speech]: {content_1}")
                
                # === Agent 2 speaks ===
                logger.info(f"[AI.Debate] Round {round_idx + 1} - {input_data.agent_2_name} is speaking...")
                
                msg_2 = await self._agent_turn(
                    name=input_data.agent_2_name,
                    llm_config_id=input_data.agent_2_llm_config,
                    system_prompt=input_data.agent_2_system_prompt,
                    context=agent_2_context,
                    input_data=input_data,
                    role="Agent 2"
                )
                
                content_2 = msg_2.content
                thought_2 = msg_2.thought
                
                log_entry_2 = {
                    "round": round_idx + 1,
                    "role": input_data.agent_2_name,
                    "type": "Agent 2",
                    "thought": thought_2,
                    "content": content_2
                }
                full_log.append(log_entry_2)
                history_public.append({"role": input_data.agent_2_name, "content": content_2})
                
                # Update the context
                agent_2_context.append(f"[My speech]: {content_2}")
                agent_1_context.append(f"[{input_data.agent_2_name}]: {content_2}")
                
                # 3. Report progress (one debate round completed)
                completed_rounds = round_idx + 1
                progress_percent = (completed_rounds / input_data.max_rounds) * 100
                
                logger.info(f"[AI.Debate] Pushing progress: {progress_percent:.1f}% ({completed_rounds}/{input_data.max_rounds})")
                
                yield ProgressEvent(
                    percent=progress_percent,
                    message=f"Round {completed_rounds}/{input_data.max_rounds} of debate completed",
                    data={
                        'completed_rounds': completed_rounds,
                        'history_public': history_public,
                        'full_log': full_log,
                        'agent_1_context': agent_1_context,
                        'agent_2_context': agent_2_context
                    }
                )
                
            except Exception as e:
                logger.error(f"[AI.Debate] Error in round {round_idx + 1}: {e}", exc_info=True)
                # Stop the debate on error and return the current result
                break
        
        # 4. Return the final result
        logger.info(f"[AI.Debate] Debate completed, {completed_rounds} rounds in total")
        
        yield DebateOutput(
            summary=history_public[-1]["content"] if history_public else "Debate not completed",
            history=history_public,
            full_log=full_log,
            total_rounds=completed_rounds
        )

    async def _agent_turn(
        self,
        name: str,
        llm_config_id: int,
        system_prompt: str,
        context: List[str],
        input_data: DebateInput,
        role: str
    ) -> DebateMessage:
        """Execute a single Agent's turn (uses generate_structured)"""
        try:
            # Build the user_prompt (merge the context)
            user_prompt = "\n\n".join(context)
            
            # Use the generate_structured function (includes quota management, retry, token stats)
            response = await generate_structured(
                session=self.context.session,
                llm_config_id=llm_config_id,
                user_prompt=user_prompt,
                output_type=DebateMessage,
                system_prompt=system_prompt,
                temperature=input_data.temperature,
                max_tokens=input_data.max_tokens,
                max_retries=3
            )
            
            logger.info(f"[AI.Debate] {role} ({name}) speech completed")
            return response
            
        except Exception as e:
            logger.error(f"[AI.Debate] {role} ({name}) call failed: {e}", exc_info=True)
            # Raise the exception on error to let the outer layer handle it
            raise