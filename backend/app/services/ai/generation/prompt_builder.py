"""System Prompt builder utilities

Responsible for building the complete System Prompt for instruction-stream generation.
"""

import json
from typing import Dict, Any, Optional
from sqlmodel import Session

from app.services import prompt_service


# Fallback hardcoded instruction guide (used when the prompt file does not exist)
FALLBACK_INSTRUCTION_GUIDE = """## Instruction-stream generation spec

You need to generate content using the instruction-stream approach. The instruction stream lets you freely mix natural-language thinking with JSON instructions, building the target data structure step by step.

## Available instructions

1. **Set a field value**
   ```json
   {"op":"set","path":"<path>","value":<value>}
   ```
   - You can set values of any type: string, number, boolean, object, array
   - Path format: JSON Pointer (e.g. /name, /age, /config/theme), always start with `/`
   - Example: {"op":"set","path":"/name","value":"Lin Feng"}
   - Example (array): {"op":"set","path":"/tags","value":["hot-blooded","fantasy"]}  <-- note: must include the "value" key

2. **Append an element to an array**
   ```json
   {"op":"append","path":"<array path>","value":<element>}
   ```
   - Used to add elements to an array one by one
   - Example: {"op":"append","path":"/hobbies","value":"reading"}

3. **Generation complete**
   ```json
   {"op":"done"}
   ```
   - Indicates that all fields have been generated
   - The system will automatically validate data integrity

## Output format requirements

1. **Each JSON instruction must be on its own line** and be a complete JSON object
2. **You may freely mix natural language and instructions**, for example:
   ```
   Let me first think about the character's background...
   {"op":"set","path":"/name","value":"Lin Feng"}
   This name fits the martial-arts setting well
   {"op":"set","path":"/age","value":25}
   ```

3. **You may interact with the user**:
   - If you encounter details that need user confirmation, you may ask in natural language
   - The user will reply in the input box, and you will see their answer
   - But please prioritize the requirements in the task description and avoid over-asking

4. **Suggested generation order**:
   - Set simple fields first (e.g. name, age)
   - Then set complex fields (e.g. nested objects)
   - For arrays, use append to add elements one by one

5. **Completion marker**:
   - After generating all required fields, output {"op":"done"}
   - The system will automatically validate; if anything is missing it will prompt you to fill it in

## Important notes

- Ensure the generated values match the field type and description
- Generate only one or a few related fields at a time, do not generate everything at once
- Keep the output natural and fluent; you may use natural language to express your thinking process
- JSON instructions must strictly conform to the format so they can be parsed correctly
- For `path`, prefer the JSON Pointer form `/field_name`; do not omit the leading `/`
- After all required fields are generated, be sure to output {"op":"done"} to indicate completion
"""


def build_instruction_system_prompt(
    session: Session,
    schema: Dict[str, Any],
    card_prompt: Optional[str] = None
) -> str:
    """Build the System Prompt for instruction-stream generation

    Components:
    1. Card task prompt (role positioning + task description)
    2. Instruction-stream generation spec
    3. JSON Schema (target data structure)

    Args:
        session: Database session
        schema: JSON Schema of the target data structure
        card_prompt: Custom prompt for the card type

    Returns:
        The complete System Prompt
    """
    parts = []

    # Explicit language directive
    parts.append('IMPORTANT: Please respond and generate all content in English only.')

    # 1. Card task prompt (if any)
    if card_prompt:
        parts.append(card_prompt)

    # 2. Load the instruction spec guide
    instruction_guide = FALLBACK_INSTRUCTION_GUIDE
    try:
        prompt = prompt_service.get_prompt_by_name(session, "Instruction Flow Generation Spec")
        if prompt and prompt.template:
            instruction_guide = prompt.template
    except Exception:
        pass
    parts.append(instruction_guide)

    # 3. JSON Schema definition
    schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
    schema_section = f"\n## Target data structure (JSON Schema)\n\n```json\n{schema_json}\n```\n\nPlease refer to this Schema and use the instruction stream to generate content step by step."
    parts.append(schema_section)

    return "\n\n".join(parts)


def build_user_task_prompt(
    user_prompt: str,
    context_info: Optional[str] = None,
    current_data: Optional[Dict[str, Any]] = None
) -> str:
    """Build the user task prompt (the first User message)

    Components:
    1. Context injection info
    2. User requirements
    3. Existing data (if continuing generation)

    Note: The card task description and Schema are already in the System Prompt, so they are not repeated here.

    Args:
        user_prompt: The user's requirements
        context_info: Context injection info
        current_data: Current existing data

    Returns:
        The complete user task prompt
    """
    parts = []

    # Explicit language directive
    parts.append('IMPORTANT: Please respond and generate all content in English only.')

    # 1. Context info (if any)
    if context_info:
        parts.append(f"## Relevant context\n\n{context_info}")

    # 2. User requirements
    if user_prompt:
        parts.append(f"## User requirements\n\n{user_prompt}")
    else:
        parts.append("Please start generating card content")

    # 3. Existing data (if continuing generation)
    if current_data:
        current_data_json = json.dumps(current_data, indent=2, ensure_ascii=False)
        parts.append(f"## Currently generated data\n\n```json\n{current_data_json}\n```\n\nPlease continue generating the missing fields.")

    return "\n\n".join(parts)