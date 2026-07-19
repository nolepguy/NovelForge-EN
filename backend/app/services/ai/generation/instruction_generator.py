"""Instruction-stream generation service

Responsible for calling the LLM to generate instruction streams, with real-time
validation and automatic repair.
"""

import json
import re
import asyncio
from typing import AsyncIterator, Dict, Any, List, Optional
from sqlmodel import Session
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from pydantic import ValidationError
from loguru import logger

from app.services.ai.core.chat_model_factory import build_chat_model
from app.services.ai.core.quota_manager import precheck_quota, record_usage
from app.services.ai.core.token_utils import estimate_tokens
from app.services.ai.core.model_builder import build_model_from_json_schema
from app.services.ai.generation.instruction_validator import (
    validate_instruction,
    apply_instruction,
    format_validation_errors
)
from app.services.ai.generation.prompt_builder import build_user_task_prompt
from app.schemas.instruction import ConversationMessage


def _estimate_messages_input_tokens(messages: List[BaseMessage]) -> int:
    parts: List[str] = []
    for msg in messages:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            parts.append(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
                elif isinstance(block, str):
                    parts.append(block)
    return estimate_tokens("\n".join(parts))


async def generate_instruction_stream(
    session: Session,
    llm_config_id: int,
    user_prompt: str,
    system_prompt: str,
    schema: Dict[str, Any],
    current_data: Dict[str, Any],
    conversation_context: List[ConversationMessage],
    context_info: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout: float = 150,
    max_retry: int = 3,
    track_stats: bool = True,
) -> AsyncIterator[Dict[str, Any]]:
    """Generate an instruction stream (with auto validation and repair)

    Args:
        session: Database session
        llm_config_id: LLM config ID
        user_prompt: The prompt entered by the user
        system_prompt: System prompt
        schema: The JSON Schema of the target data structure
        current_data: Currently generated data
        conversation_context: Conversation history
        temperature: Sampling temperature
        max_tokens: Maximum number of generated tokens
        timeout: Timeout
        max_retry: Maximum number of retries

    Yields:
        Event dict, containing type and the corresponding data
    """
    # Build the ChatModel
    try:
        chat_model = build_chat_model(
            session=session,
            llm_config_id=llm_config_id,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    except Exception as e:
        logger.error(f"Failed to build ChatModel: {e}")
        yield {
            "type": "error",
            "text": f"Failed to initialize LLM: {str(e)}"
        }
        return

    # Create a Pydantic dynamic model (for final validation)
    try:
        DynamicModel = build_model_from_json_schema('DynamicResponseModel', schema)
    except Exception as e:
        logger.error(f"Failed to create dynamic model: {e}")
        yield {
            "type": "error",
            "text": f"Schema parsing failed: {str(e)}"
        }
        return

    # Collect generated data (deep copy to avoid modifying the original data)
    collected_data = dict(current_data)

    # Build the message history
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]

    # If this is the first generation (conversation_context is empty), build the first user message
    if not conversation_context:
        # Build the first user message: context + user requirements + existing data
        # (the task description and Schema are already in the System Prompt)
        task_prompt = build_user_task_prompt(
            user_prompt=user_prompt or "Please start generating card content",
            context_info=context_info,
            current_data=collected_data if collected_data else None
        )
        messages.append(HumanMessage(content=task_prompt))
    else:
        # Continue generation: add the conversation history context
        for msg in conversation_context:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        # Always append the currently generated data info at the end (if any)
        # so the LLM knows the current state and avoids regenerating existing fields
        if collected_data:
            current_data_info = f"\n\n## Currently generated data\n\n```json\n{json.dumps(collected_data, ensure_ascii=False, indent=2)}\n```\n\nPlease continue generating the missing fields; do not regenerate fields that already exist."

            # If the last message is a user message, append to that message
            if messages and isinstance(messages[-1], HumanMessage):
                messages[-1].content += current_data_info
            else:
                # Otherwise create a new user message
                messages.append(HumanMessage(content=current_data_info))

    # Print the full message context (for debugging)
    # logger.info("=" * 80)
    # logger.info(f"[Instruction generation] starting generation, {len(messages)} messages in total")
    # for idx, msg in enumerate(messages):
    #     msg_type = type(msg).__name__
    #     content_preview = msg.content
    #     logger.info(f"  [{idx}] {msg_type}: {content_preview}")
    # logger.info("=" * 80)

    # Start the generation loop (supports auto repair)
    failed_instructions = []  # accumulated failed instructions
    generation_completed = False  # flag whether it finished normally

    for attempt in range(max_retry):
        logger.info(f"[Generation round {attempt + 1}/{max_retry}] starting generation...")
        attempt_input_tokens = _estimate_messages_input_tokens(messages)
        if track_stats:
            ok, reason = precheck_quota(
                session,
                llm_config_id,
                attempt_input_tokens,
                need_calls=1,
            )
            if not ok:
                yield {
                    "type": "error",
                    "text": f"Insufficient LLM quota: {reason}",
                }
                return

        attempt_output_text = ""
        attempt_started = False
        attempt_aborted = False
        try:
            # Stream-call the LLM
            buffer = ""
            ai_output_lines = []  # record all AI output (for feedback)
            need_fix = False  # whether a repair is needed (integrity check failed)
            fix_prompt = ""  # repair prompt
            should_break_stream = False  # whether the stream should be interrupted

            json_buffer = ""  # JSON accumulation buffer
            brace_depth = 0  # brace depth
            in_string = False  # whether inside a string
            escape_next = False  # whether the next char is escaped

            attempt_started = True
            async for chunk in chat_model.astream(messages):
                raw = getattr(chunk, "content", "")
                if isinstance(raw, str):
                    content = raw
                elif isinstance(raw, list):
                    parts = []
                    for part in raw:
                        if isinstance(part, dict):
                            # Only concatenate text to avoid reasoning/tool fragments
                            # polluting your subsequent JSON line parsing
                            if part.get("type") == "text" and isinstance(part.get("text"), str):
                                parts.append(part["text"])
                        elif isinstance(part, str):
                            parts.append(part)
                    content = "".join(parts)
                else:
                    content = str(raw) if raw is not None else ""

                if not content:
                    continue

                attempt_output_text += content
                buffer += content

                # Parse line by line
                lines = buffer.split('\n')
                buffer = lines[-1]  # keep the incomplete line

                for line in lines[:-1]:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue

                    ai_output_lines.append(line_stripped)  # record output

                    # Process character by character, accumulating complete JSON objects
                    instruction = None
                    for char in line:
                        # Handle escapes
                        if escape_next:
                            if brace_depth > 0:
                                json_buffer += char
                            escape_next = False
                            continue

                        if char == '\\':
                            if brace_depth > 0:
                                json_buffer += char
                            escape_next = True
                            continue

                        # Handle string boundaries
                        if char == '"' and brace_depth > 0:
                            in_string = not in_string
                            json_buffer += char
                            continue

                        # Only count braces outside of strings
                        if not in_string:
                            if char == '{':
                                brace_depth += 1
                                json_buffer += char
                            elif char == '}':
                                json_buffer += char
                                brace_depth -= 1

                                # JSON object complete
                                if brace_depth == 0:
                                    instruction = try_parse_instruction(json_buffer)
                                    if not instruction:
                                        # Parsing failed, possibly invalid JSON
                                        logger.warning(f"JSON parsing failed: {json_buffer}")
                                        # Try to fix common errors (e.g. trailing commas)
                                        try:
                                            # Simple cleanup logic, can be enhanced as needed
                                            cleaned_json = json_buffer.replace(",}", "}").replace(",]", "]")
                                            instruction = try_parse_instruction(cleaned_json)
                                        except Exception:
                                            pass

                                        if not instruction:
                                            # JSON parsing failed, accumulate the error
                                            failed_instructions.append({
                                                "instruction": json_buffer[:100],
                                                "error": "JSON parsing failed"
                                            })
                                            yield {
                                                "type": "warning",
                                                "text": f"Unable to parse instruction JSON: {json_buffer[:50]}..."
                                            }
                                            # JSON parsing failed; accumulate the error but do not
                                            # interrupt immediately; let the LLM keep generating.
                                            # Only force-interrupt when too many errors accumulate
                                            if len(failed_instructions) >= 5:
                                                should_break_stream = True

                                    json_buffer = ""
                                    if instruction:
                                        break  # found the instruction, process it
                            elif brace_depth > 0:
                                json_buffer += char
                        elif brace_depth > 0:
                            json_buffer += char

                    if instruction:
                        # ... (existing instruction processing logic) ...
                        # Parsed successfully, validate the instruction
                        try:
                            # ...
                            validate_instruction(instruction, schema)
                            apply_instruction(collected_data, instruction)
                            yield {
                                "type": "instruction",
                                "instruction": instruction
                            }

                            # done logic ...
                            if instruction.get('op') == 'done':
                                logger.info("[Done instruction] received done instruction, preparing for final validation...")

                                # 1. Check whether there are accumulated instruction errors
                                has_instruction_errors = len(failed_instructions) > 0

                                # 2. Use Pydantic to perform data integrity validation
                                validation_errors = []
                                try:
                                    validated_model = DynamicModel(**collected_data)
                                except ValidationError as e:
                                    # Format the Pydantic errors
                                    validation_errors = e.errors()

                                # 3. If there are any issues (instruction errors OR data validation failures),
                                #    reject completion and feed back
                                if has_instruction_errors or validation_errors:
                                    logger.warning(f"[Done rejected] instruction errors: {len(failed_instructions)}, data validation issues: {len(validation_errors)}")

                                    feedback_parts = []

                                    # Build instruction-error feedback
                                    if failed_instructions:
                                        feedback_parts.append("[Instruction execution failed] The following instructions failed to parse or execute:")
                                        for item in failed_instructions:
                                            feedback_parts.append(f"- {item['error']}: {str(item['instruction'])[:100]}")

                                    # Build data-integrity feedback
                                    if validation_errors:
                                        feedback_parts.append("\n[Data integrity missing] The following fields failed validation:")
                                        feedback_parts.append(format_validation_errors(validation_errors))

                                    feedback_text = "\n".join(feedback_parts)

                                    # Set the repair flag
                                    need_fix = True
                                    fix_prompt = f"""You sent a done instruction, but there were errors or incomplete data during generation:

{feedback_text}

Currently successfully applied data state:
```json
{json.dumps(collected_data, ensure_ascii=False, indent=2)}
```

Please fix the above instruction errors and fill in the missing required fields.
**Important**: Do not explain; directly output the JSON instructions (set/append) used for the fix, and after fixing output {{"op":"done"}} again
"""
                                    should_break_stream = True
                                else:
                                    # Everything is perfect, pass!
                                    logger.info("[Done instruction] validation passed perfectly!")
                                    generation_completed = True
                                    yield {
                                        "type": "done",
                                        "success": True,
                                        "message": "Generation complete",
                                        "final_data": validated_model.model_dump(mode='json')
                                    }
                                    return

                        except ValueError as e:
                            logger.warning(f"Instruction validation failed: {e}")
                            failed_instructions.append({"instruction": instruction, "error": str(e)})
                            yield {"type": "warning", "text": f"Instruction validation failed: {str(e)}"}
                            # Instruction validation failed; accumulate the error but do not interrupt, continue
                            # should_break_stream = True

                    else:
                        # Not a JSON instruction, treat as natural-language thinking
                        # Only output when not in the middle of JSON accumulation
                        if brace_depth == 0 and line_stripped:
                             yield {
                                "type": "thinking",
                                "text": line
                            }

                # Check whether the stream needs to be interrupted
                if should_break_stream:
                    break
            # Handle the leftover JSON buffer (the last part of a multi-line JSON)
            if json_buffer.strip() and brace_depth == 0:
                instruction = try_parse_instruction(json_buffer.strip())
                if instruction:
                    try:
                        validate_instruction(instruction, schema)
                        apply_instruction(collected_data, instruction)
                        yield {
                            "type": "instruction",
                            "instruction": instruction
                        }
                    except ValueError as e:
                        logger.warning(f"Leftover JSON instruction validation failed: {e}")

            # Handle the last line (if any)
            if buffer.strip():
                instruction = try_parse_instruction(buffer.strip())
                if instruction:
                    try:
                        validate_instruction(instruction, schema)
                        apply_instruction(collected_data, instruction)
                        yield {
                            "type": "instruction",
                            "instruction": instruction
                        }

                        if instruction.get('op') == 'done':
                            try:
                                validated_model = DynamicModel(**collected_data)
                                yield {
                                    "type": "done",
                                    "success": True,
                                    "message": "Generation complete",
                                    # Pass the final validated data (including injected defaults) back to the
                                    # frontend to ensure consistency
                                    "final_data": validated_model.model_dump(mode='json')
                                }
                                return
                            except ValidationError as e:
                                error_msg = format_validation_errors(e.errors())
                                logger.warning(f"Integrity validation failed: {error_msg}")
                                # Set the repair flag, prepare to feed back to the LLM
                                need_fix = True
                                fix_prompt = f"""The generated data is incomplete or incorrect; please fix the following issues:

{error_msg}

Current data:
```json
{json.dumps(collected_data, ensure_ascii=False, indent=2)}
```

Please continue generating the missing or incorrect fields, and output {{"op":"done"}} again when done
"""
                                should_break_stream = True
                    except ValueError as e:
                        logger.warning(f"Instruction validation failed: {e}")
                else:
                    yield {
                        "type": "thinking",
                        "text": buffer.strip()
                    }

            # After the stream ends, handle various situations

            # Case 1: integrity validation failed, repair needed
            if need_fix:
                logger.info(f"Integrity validation failed, will feed back to the LLM to regenerate (attempt {attempt + 1}/{max_retry})")

                # Add the AI output and the repair prompt to the conversation history
                messages.append(AIMessage(content="\n".join(ai_output_lines)))
                messages.append(HumanMessage(content=fix_prompt))

                # Wait before retrying to avoid immediate retries triggering rate limits
                if attempt < max_retry - 1:
                    retry_delay = min(2 ** attempt, 5)  # exponential backoff: 1s, 2s, 4s...
                    logger.info(f"Waiting {retry_delay} seconds before retry...")
                    await asyncio.sleep(retry_delay)

                # Continue to the next generation round
                continue

            # Case 2: instruction validation failed, needs to be fed back to the LLM
            if failed_instructions:
                # Build the error feedback message
                error_summary = "\n".join([
                    f"- Instruction: {json.dumps(item['instruction'], ensure_ascii=False)}\n  Error: {item['error']}"
                    for item in failed_instructions
                ])

                feedback_prompt = f"""
The following {len(failed_instructions)} instructions you generated failed validation:

{error_summary}

Currently successfully applied data:
```json
{json.dumps(collected_data, ensure_ascii=False, indent=2)}
```

Please note:
1. Check whether the field path is correct
2. For array fields, ensure the field is an array type before using the append operation
3. For object fields, use set to set the whole object or use a nested path to set sub-fields
4. Refer to the Schema definition to ensure the operator matches the field type

Please fix these errors and continue generating, and output {{"op":"done"}} when done
"""

                logger.info(f"Feeding {len(failed_instructions)} failed instructions back to the LLM, regenerating")

                # Add the AI output and the feedback to the conversation history
                messages.append(AIMessage(content="\n".join(ai_output_lines)))
                messages.append(HumanMessage(content=feedback_prompt))

                # Clear the failure list, prepare for the next round
                failed_instructions = []

                # Wait before retrying to avoid immediate retries triggering rate limits
                if attempt < max_retry - 1:
                    retry_delay = min(2 ** attempt, 5)  # exponential backoff: 1s, 2s, 4s...
                    logger.info(f"Waiting {retry_delay} seconds before retry...")
                    await asyncio.sleep(retry_delay)

                # Continue to the next generation round
                continue

            # If the stream ended but there was no done instruction, it may be a max_tokens limit or other reason
            logger.warning("LLM stream ended but no done instruction received")
            logger.info(f"Currently collected data fields: {list(collected_data.keys())}")

            # Attempt an implicit completion (try validation)
            try:
                # Use the Pydantic model for final validation
                validated_model = DynamicModel(**collected_data)

                yield {
                    "type": "done",
                    "success": True,
                    "message": "Generation ended (auto-completed)",
                    "final_data": validated_model.model_dump(mode='json')
                }
                generation_completed = True
                break
            except Exception as e:
                 logger.warning(f"Implicit validation after the stream ended failed: {e}")
                 # If validation really failed, it may have been truncated; user feedback or retry is needed
                 # (we do not auto-retry here since this is already the last attempt)
                 pass
            logger.info(f"Current data: {json.dumps(collected_data, ensure_ascii=False, indent=2)[:500]}...")

            # Try to validate the integrity of the current data
            try:
                validated_model = DynamicModel(**collected_data)

                # Check whether any Optional fields are missing (possibly truncated)
                schema_properties = schema.get("properties", {})
                missing_optional_fields = []
                for field_name, field_schema in schema_properties.items():
                    # Check whether it is an Optional field (not in required)
                    is_optional = field_name not in schema.get("required", [])
                    # If it is an Optional field but not in the data (or is an empty list/empty string)
                    if is_optional:
                        field_value = collected_data.get(field_name)
                        if field_value is None or field_value == [] or field_value == "":
                            missing_optional_fields.append(field_name)

                # If Optional fields are missing, it is very likely a max_tokens truncation
                if missing_optional_fields:
                    logger.warning(f"Although required fields are complete, the following Optional fields are missing: {missing_optional_fields}")
                    logger.warning("Combined with the LLM not sending a done instruction, suspect max_tokens truncation")
                    yield {
                        "type": "warning",
                        "text": f"Generation was truncated (LLM did not send a done instruction). The following fields are missing: {', '.join(missing_optional_fields)}.\n\nPossible reasons:\n1. max_tokens is set too small (recommend increasing it)\n2. Network fluctuation or service rate limiting\n\nSuggestion: retry later or adjust the parameters."
                    }
                    # Try to repair
                    if attempt < max_retry - 1:
                        logger.info(f"Attempting to auto-fill the missing fields (attempt {attempt + 1}/{max_retry})")
                        fix_prompt = f"""
Generation is incomplete; the following fields are missing: {', '.join(missing_optional_fields)}

Current data:
```json
{json.dumps(collected_data, ensure_ascii=False, indent=2)}
```

Please continue generating the missing fields, and output {{"op":"done"}} when done
"""
                        messages.append(AIMessage(content="\n".join(ai_output_lines)))
                        messages.append(HumanMessage(content=fix_prompt))

                        # Wait before retrying
                        retry_delay = min(2 ** attempt, 5)
                        logger.info(f"Waiting {retry_delay} seconds before retry...")
                        await asyncio.sleep(retry_delay)

                        continue
                    else:
                        # Last round; directly return incomplete data
                        logger.warning("Reached the maximum number of retries, returning incomplete data")
                        generation_completed = True
                        yield {
                            "type": "done",
                            "success": True,
                            "message": f"Generation complete (some fields missing: {', '.join(missing_optional_fields)})"
                        }
                        return

                # All fields have values, data is complete
                logger.info("Data integrity validation passed; although there was no done instruction, the data is complete")
                generation_completed = True
                yield {
                    "type": "done",
                    "success": True,
                    "message": "Generation complete (LLM did not send a done instruction, but the data is complete)"
                }
                return
            except ValidationError as e:
                # Data is incomplete, possibly the output was truncated due to max_tokens limits
                error_msg = format_validation_errors(e.errors())
                logger.warning(f"Data is incomplete: {error_msg}")

                # Check whether it failed on the first round (max_tokens may be too small)
                if attempt == 0:
                    yield {
                        "type": "error",
                        "text": f"Generation was truncated. Possible reasons:\n1. max_tokens is set too small (recommend increasing it)\n2. Network fluctuation or service rate limiting\n\nSuggestion: retry later or adjust the parameters."
                    }
                    logger.error("Truncated on the first round; strongly suspect max_tokens is too small")
                    break

                # Otherwise attempt a repair
                logger.info(f"Attempting to auto-repair the missing fields (attempt {attempt + 1}/{max_retry})")
                need_fix = True
                fix_prompt = f"""
Generation was interrupted and the data is incomplete. Missing or incorrect fields:

{error_msg}

Current data:
```json
{json.dumps(collected_data, ensure_ascii=False, indent=2)}
```

Please continue generating the missing fields, and output {{"op":"done"}} when done
"""
                messages.append(AIMessage(content="\n".join(ai_output_lines)))
                messages.append(HumanMessage(content=fix_prompt))

                # Wait before retrying
                if attempt < max_retry - 1:
                    retry_delay = min(2 ** attempt, 4)
                    logger.info(f"Waiting {retry_delay} seconds before retry...")
                    await asyncio.sleep(retry_delay)

                continue

        except asyncio.CancelledError:
            attempt_aborted = True
            raise
        except Exception as e:
            logger.error(f"Error during generation: {e}")
            yield {
                "type": "error",
                "text": f"Generation failed: {str(e)}"
            }
            break
        finally:
            if attempt_started and track_stats:
                try:
                    record_usage(
                        session,
                        llm_config_id,
                        attempt_input_tokens,
                        estimate_tokens(attempt_output_text),
                        calls=1,
                        aborted=attempt_aborted,
                    )
                except Exception as usage_error:
                    logger.warning(f"Failed to record instruction-stream token statistics: {usage_error}")

    # Only report failure when it did not finish normally
    if not generation_completed:
        logger.error(f"Generation failed: reached the maximum number of retries {max_retry}")
        yield {
            "type": "error",
            "text": f"Generation failed: reached the maximum number of retries {max_retry}"
        }


def try_parse_instruction(line: str) -> Optional[Dict[str, Any]]:
    """Try to parse a line of text into a JSON instruction

    Args:
        line: The text line

    Returns:
        The instruction dict if parsing succeeds, otherwise None
    """
    # Remove possible markdown code-block markers
    line = line.strip()
    if line.startswith('```') or line.endswith('```'):
        return None

    # Try to parse JSON directly
    try:
        obj = json.loads(line)
        if isinstance(obj, dict) and 'op' in obj:
            return obj
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON object (supports nested structures)
    # Scan character by character, matching a complete JSON object
    start_idx = line.find('{')
    if start_idx == -1:
        return None

    # Starting from the first {, match a complete JSON object
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(line)):
        char = line[i]

        # Handle characters inside a string
        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        # Only count braces outside of strings
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1

                # Found the matching closing brace
                if brace_count == 0:
                    json_str = line[start_idx:i+1]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict) and 'op' in obj:
                            return obj
                    except json.JSONDecodeError:
                        # Continue searching for the next possible JSON object
                        next_start = line.find('{', i+1)
                        if next_start != -1:
                            start_idx = next_start
                            brace_count = 0
                            in_string = False
                            escape_next = False
                        else:
                            return None

    return None