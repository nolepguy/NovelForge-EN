"""Instruction validation utilities

Responsible for validating the format, path, type, and constraints of instructions.
"""

import re
from typing import Dict, Any, Optional
from pydantic import ValidationError
from loguru import logger


_ARRAY_INDEX_PATTERN = re.compile(r"\[(\d+)\]")


def normalize_instruction_path(path: Any) -> str:
    """Normalize common path notations into a JSON Pointer."""
    if not isinstance(path, str):
        return ""

    normalized = path.strip()
    if not normalized:
        return ""

    if normalized == "$":
        return "/"
    if normalized.startswith("$."):
        normalized = normalized[2:]

    # items[0] -> items/0
    normalized = _ARRAY_INDEX_PATTERN.sub(r"/\1", normalized)
    # config.theme -> config/theme
    normalized = normalized.replace(".", "/")

    if not normalized.startswith("/"):
        normalized = "/" + normalized.lstrip("/")

    while "//" in normalized:
        normalized = normalized.replace("//", "/")

    return normalized



def resolve_schema(schema: Dict[str, Any], root_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve Schema references ($ref) and combined types (allOf)

    Args:
        schema: Current Schema node
        root_schema: Root Schema (contains $defs/definitions)

    Returns:
        The resolved Schema
    """
    if not isinstance(schema, dict):
        return schema

    resolved = schema

    # 1. Handle $ref
    if '$ref' in resolved:
        ref_path = resolved['$ref']
        # Supports #/$defs/Name and #/definitions/Name
        if ref_path.startswith('#/'):
            parts = ref_path.split('/')
            # parts[0] is '#', parts[1] is '$defs' or 'definitions', parts[2] is model name
            if len(parts) >= 3:
                def_section = parts[1]
                model_name = parts[2]
                if def_section in root_schema and model_name in root_schema[def_section]:
                    # Recursively resolve (handle Ref -> Ref cases)
                    return resolve_schema(root_schema[def_section][model_name], root_schema)

    # 2. Handle allOf (merge properties)
    if 'allOf' in resolved:
        merged = {}
        for sub_schema in resolved['allOf']:
            sub_resolved = resolve_schema(sub_schema, root_schema)
            if isinstance(sub_resolved, dict):
                # Simple merge of properties
                if 'properties' in sub_resolved:
                    if 'properties' not in merged:
                        merged['properties'] = {}
                    merged['properties'].update(sub_resolved['properties'])
                # Merge required
                if 'required' in sub_resolved:
                    if 'required' not in merged:
                        merged['required'] = []
                    merged['required'].extend(sub_resolved['required'])
                # Merge type
                if 'type' in sub_resolved and 'type' not in merged:
                    merged['type'] = sub_resolved['type']

        # Also merge the current schema's other attributes in
        for k, v in resolved.items():
            if k != 'allOf':
                if k == 'properties':
                    if 'properties' not in merged:
                        merged['properties'] = {}
                    merged['properties'].update(v)
                elif k == 'required':
                    if 'required' not in merged:
                        merged['required'] = []
                    new_reqs = [r for r in v if r not in merged['required']]
                    merged['required'].extend(new_reqs)
                else:
                    merged[k] = v
        return merged

    return resolved


def get_field_schema_by_path(schema: Dict[str, Any], path: str) -> Optional[Dict[str, Any]]:
    """Get a field's Schema by its JSON Pointer path

    Args:
        schema: The complete JSON Schema
        path: A path in JSON Pointer format, e.g. /name or /config/theme

    Returns:
        The field's Schema, or None if the path does not exist
    """
    path = normalize_instruction_path(path)
    if not path or not path.startswith('/'):
        return None

    # Remove the leading /
    path = path[1:]
    if not path:
        return schema

    # Split the path
    parts = path.split('/')
    current_schema = schema

    for part in parts:
        # Try to resolve references at each level
        current_schema = resolve_schema(current_schema, schema)

        # Handle array indices (e.g. hobbies/0)
        if part.isdigit():
            # Array element, get the items schema
            if 'items' in current_schema:
                current_schema = current_schema['items']
            elif 'prefixItems' in current_schema:
                 # Handle tuple (prefixItems)
                 idx = int(part)
                 if idx < len(current_schema['prefixItems']):
                     current_schema = current_schema['prefixItems'][idx]
                 else:
                     return None
            else:
                # Try to handle the array case in anyOf/oneOf
                found_array = False
                for key in ['anyOf', 'oneOf']:
                    if key in current_schema:
                        for option in current_schema[key]:
                            resolved_option = resolve_schema(option, schema)
                            if resolved_option.get('type') == 'array' and 'items' in resolved_option:
                                current_schema = resolved_option['items']
                                found_array = True
                                break
                        if found_array:
                            break
                if not found_array:
                    return None
        else:
            # Object property
            # Try to handle properties
            if 'properties' in current_schema and part in current_schema['properties']:
                current_schema = current_schema['properties'][part]
            else:
                # Try to handle the object case in anyOf/oneOf (e.g. Union[A, B])
                # This is a simplified handling: as long as the property is found in any branch,
                # the path is considered valid from the Schema's perspective, and the found
                # property's Schema is returned.
                # Note: this may be less strict during validation (since we don't know at runtime
                # whether it's A or B), but for a "does the path exist" check, this is a reasonable
                # lenient policy.
                found_prop = False
                for key in ['anyOf', 'oneOf']:
                    if key in current_schema:
                        for option in current_schema[key]:
                            resolved_option = resolve_schema(option, schema)
                            if 'properties' in resolved_option and part in resolved_option['properties']:
                                current_schema = resolved_option['properties'][part]
                                found_prop = True
                                break
                        if found_prop:
                            break

                if not found_prop:
                    return None

    # Resolve once more before returning
    return resolve_schema(current_schema, schema)


def validate_type(value: Any, expected_type: Optional[str]) -> bool:
    """Validate whether the value's type matches

    Args:
        value: The value to validate
        expected_type: The expected type (JSON Schema type)

    Returns:
        Whether it matches
    """
    if expected_type is None:
        return True

    type_mapping = {
        'string': str,
        'integer': int,
        'number': (int, float),
        'boolean': bool,
        'array': list,
        'object': dict,
        'null': type(None)
    }

    expected_python_type = type_mapping.get(expected_type)
    if expected_python_type is None:
        # Unknown type, handle leniently
        return True

    return isinstance(value, expected_python_type)


def _resolve_schema_variant_by_type(
    schema_node: Dict[str, Any],
    root_schema: Dict[str, Any],
    target_type: str,
) -> Optional[Dict[str, Any]]:
    """Select the target-type branch from a nullable/union schema."""
    resolved = resolve_schema(schema_node, root_schema)
    if resolved.get('type') == target_type:
        return resolved

    for union_key in ('anyOf', 'oneOf'):
        options = resolved.get(union_key)
        if not isinstance(options, list):
            continue
        for option in options:
            resolved_option = resolve_schema(option, root_schema)
            if resolved_option.get('type') == target_type:
                return resolved_option
    return None


def _validate_constraints(value: Any, schema_node: Dict[str, Any], path: str) -> None:
    """Validate constraints such as enum, length, and numeric range."""
    expected_type = schema_node.get('type')

    if 'enum' in schema_node and value not in schema_node['enum']:
        raise ValueError(f"Value of field {path} is not within the enum range: {schema_node['enum']}")

    if expected_type in ['integer', 'number']:
        if 'minimum' in schema_node and value < schema_node['minimum']:
            raise ValueError(f"Value {value} of field {path} is less than the minimum {schema_node['minimum']}")
        if 'maximum' in schema_node and value > schema_node['maximum']:
            raise ValueError(f"Value {value} of field {path} is greater than the maximum {schema_node['maximum']}")

    if expected_type == 'string':
        if 'minLength' in schema_node and len(value) < schema_node['minLength']:
            raise ValueError(f"Length {len(value)} of field {path} is less than the minimum length {schema_node['minLength']}")
        if 'maxLength' in schema_node and len(value) > schema_node['maxLength']:
            raise ValueError(f"Length {len(value)} of field {path} is greater than the maximum length {schema_node['maxLength']}")

    if expected_type == 'array' and isinstance(value, list):
        if 'minItems' in schema_node and len(value) < schema_node['minItems']:
            raise ValueError(f"Length {len(value)} of array {path} is less than the minimum length {schema_node['minItems']}")
        if 'maxItems' in schema_node and len(value) > schema_node['maxItems']:
            raise ValueError(f"Length {len(value)} of array {path} is greater than the maximum length {schema_node['maxItems']}")


def validate_value_against_schema(
    value: Any,
    schema_node: Dict[str, Any],
    root_schema: Dict[str, Any],
    path: str,
) -> None:
    """Recursively validate a value against a single schema node."""
    resolved = resolve_schema(schema_node, root_schema)

    for union_key in ('anyOf', 'oneOf'):
        options = resolved.get(union_key)
        if not isinstance(options, list):
            continue

        matched = False
        last_error: Optional[ValueError] = None
        for option in options:
            resolved_option = resolve_schema(option, root_schema)
            opt_type = resolved_option.get('type')
            if not validate_type(value, opt_type):
                continue
            try:
                validate_value_against_schema(value, resolved_option, root_schema, path)
                matched = True
                break
            except ValueError as exc:
                last_error = exc

        if not matched:
            if last_error:
                raise last_error
            allowed_types = [resolve_schema(opt, root_schema).get('type') for opt in options]
            raise ValueError(
                f"Field type or structure error: path {path}, expected one of {allowed_types}. Actual: {type(value).__name__}"
            )
        return

    expected_type = resolved.get('type')
    if expected_type and not validate_type(value, expected_type):
        raise ValueError(f"Field type error: path {path}, expected {expected_type}, actual {type(value).__name__}")

    _validate_constraints(value, resolved, path)

    if expected_type == 'object':
        validate_schema_structure(value, resolved, root_schema, path)
        return

    if expected_type == 'array' and isinstance(value, list):
        if isinstance(resolved.get('prefixItems'), list):
            for idx, item_schema in enumerate(resolved['prefixItems']):
                if idx >= len(value):
                    break
                validate_value_against_schema(value[idx], item_schema, root_schema, f"{path}/{idx}")
            return

        item_schema = resolved.get('items')
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                validate_value_against_schema(item, item_schema, root_schema, f"{path}/{idx}")


def validate_instruction(instruction: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Validate the legality of a single instruction

    Args:
        instruction: The instruction object
        schema: The complete JSON Schema

    Raises:
        ValueError: Raised when validation fails
    """
    op = instruction.get('op')

    if op not in ['set', 'append', 'done']:
        raise ValueError(f"Unknown instruction operation type: {op}")

    if op == 'done':
        # done instructions need no validation
        return

    path = instruction.get('path')
    value = instruction.get('value')

    if not path:
        raise ValueError("Instruction is missing the path field")

    # Be tolerant of bare paths / dot paths occasionally emitted by the model;
    # normalize them into JSON Pointer before validating.
    path = normalize_instruction_path(path)
    instruction['path'] = path

    if value is None and op != 'set':
        raise ValueError(f"Instruction {op} is missing the value field")

    # 1. Path validation
    field_schema = get_field_schema_by_path(schema, path)
    if not field_schema:
        raise ValueError(f"Path {path} does not exist in the Schema")

    # For append operations, check the array's items type
    if op == 'append':
        actual_schema = _resolve_schema_variant_by_type(field_schema, schema, 'array')
        if not actual_schema:
            raise ValueError(f"Path {path} is not an array type, cannot use the append operation")
        items_schema = actual_schema.get('items')
        if not isinstance(items_schema, dict):
            raise ValueError(f"The array at path {path} has no items structure defined, cannot use the append operation")
        validate_value_against_schema(value, items_schema, schema, f"{path}/-")

    else:
        validate_value_against_schema(value, field_schema, schema, path)

def validate_schema_structure(
    data: Any,
    schema_node: Dict[str, Any],
    root_schema: Dict[str, Any],
    path: str = "",
) -> None:
    """Recursively validate that the data structure conforms to the Schema definition (including required and properties)

    Args:
        data: The data to validate
        schema_node: The Schema node of the current data
        root_schema: Root Schema (used to resolve $ref)

    Raises:
        ValueError: Validation failed
    """
    if not isinstance(data, dict):
        return

    resolved = resolve_schema(schema_node, root_schema)

    # 1. Iterate Schema properties, handling required validation + default injection + recursive validation
    if 'properties' in resolved:
        properties = resolved['properties']
        required_fields = set(resolved.get('required', []))

        # To support default injection, we iterate the Schema's properties rather than just the data's keys.
        # Note: if the Schema is large but the data is small, this may have efficiency concerns.
        # Given this is a generation process, the data structures are usually not too large, and for
        # completeness, iterating the Schema is reasonable.

        for field_name, field_schema_ref in properties.items():
            field_schema = resolve_schema(field_schema_ref, root_schema)

            # A. Handle missing fields
            if field_name not in data:
                # If there is a default value, inject the default
                if 'default' in field_schema:
                    data[field_name] = field_schema['default']
                # If no default and it is a required field, raise an error
                elif field_name in required_fields:
                    raise ValueError(f"Missing required field: {field_name}")
                # Neither required nor has a default, skip
                continue

            field_path = f"{path}/{field_name}" if path else f"/{field_name}"

            # B. Handle existing fields
            field_value = data[field_name]

            validate_value_against_schema(field_value, field_schema, root_schema, field_path)

    # 2. (Optional) Check whether data has extra fields? (additionalProperties)
    # Currently not strictly restricted; AI is allowed to generate extra fields as "thinking notes"
    # or undefined properties.


def apply_instruction(data: Dict[str, Any], instruction: Dict[str, Any]) -> None:
    """Apply an instruction to a data object

    Args:
        data: The data object (will be modified)
        instruction: The instruction object
    """
    op = instruction.get('op')

    if op == 'done':
        return

    path = normalize_instruction_path(instruction.get('path', ''))
    value = instruction.get('value')

    # Remove the leading /
    if path.startswith('/'):
        path = path[1:]

    if not path:
        return

    # Split the path
    parts = path.split('/')
    current = data

    # Traverse the path, creating intermediate objects
    for i, part in enumerate(parts[:-1]):
        if part.isdigit():
            # Array index
            idx = int(part)
            if not isinstance(current, list):
                logger.warning(f"{part} in path {path} should be an array index, but the current object is not an array")
                return

            # Ensure the array is long enough
            while len(current) <= idx:
                current.append({})

            current = current[idx]
        else:
            # Object property
            if part not in current:
                # Determine whether the next part is an array index
                next_part = parts[i + 1] if i + 1 < len(parts) else None
                if next_part and next_part.isdigit():
                    current[part] = []
                else:
                    current[part] = {}

            current = current[part]

    # Set the last field
    last_part = parts[-1]

    if op == 'set':
        if last_part.isdigit():
            idx = int(last_part)
            if isinstance(current, list):
                while len(current) <= idx:
                    current.append(None)
                current[idx] = value
        else:
            current[last_part] = value

    elif op == 'append':
        if last_part.isdigit():
            logger.warning(f"append operation should not use an array-index path: {path}")
            return

        # Initialize the array (if it does not exist or is None)
        if last_part not in current or current[last_part] is None:
            current[last_part] = []

        if not isinstance(current[last_part], list):
            logger.warning(f"Path {path} is not an array, cannot perform the append operation")
            return

        current[last_part].append(value)


def format_validation_errors(errors: list) -> str:
    """Format Pydantic validation errors

    Args:
        errors: Pydantic validation error list

    Returns:
        The formatted error message
    """
    lines = []
    for error in errors:
        loc = ' -> '.join(str(l) for l in error.get('loc', []))
        msg = error.get('msg', 'unknown error')
        lines.append(f"- {loc}: {msg}")

    return '\n'.join(lines)


def extract_error_fields(validation_error: ValidationError) -> list[str]:
    """Extract the list of error fields from Pydantic validation errors

    Args:
        validation_error: Pydantic validation error

    Returns:
        The list of error field paths
    """
    fields = []
    for error in validation_error.errors():
        loc = error.get('loc', ())
        if loc:
            # Convert to JSON Pointer format
            path = '/' + '/'.join(str(l) for l in loc)
            fields.append(path)

    return fields


class InstructionExecutor:
    """Instruction executor

    Encapsulates batch execution of instructions, validation, and data management logic.
    Used to unify instruction execution across AI card generation and inspiration-assistant tools.
    """

    def __init__(self, schema: Dict[str, Any], initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialize the executor

        Args:
            schema: JSON Schema
            initial_data: Initial data (optional)
        """
        self.schema = schema
        self.data = initial_data.copy() if initial_data else {}
        self.stats = {
            "executed": 0,
            "success": 0,
            "failed": 0
        }

    def execute(self, instruction: Dict[str, Any]) -> None:
        """
        Execute a single instruction

        Args:
            instruction: The instruction object

        Raises:
            ValueError: Instruction validation or execution failed
        """
        self.stats["executed"] += 1

        try:
            # Validate the instruction
            validate_instruction(instruction, self.schema)

            # Apply the instruction
            apply_instruction(self.data, instruction)

            self.stats["success"] += 1

        except Exception as e:
            self.stats["failed"] += 1
            raise

    def execute_batch(self, instructions: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute instructions in batch

        Args:
            instructions: The instruction array

        Returns:
            Execution result:
            {
                "success": bool - whether fully succeeded (all instructions executed and data complete)
                "data": dict - current data
                "applied": int - number of successfully executed instructions
                "failed": int - number of failed instructions
                "errors": list - details of failed instructions
                "is_complete": bool - whether the data is complete
                "missing_fields": list - missing required fields
            }
        """
        failed_instructions = []

        for idx, inst in enumerate(instructions):
            try:
                self.execute(inst)
            except Exception as e:
                failed_instructions.append({
                    "index": idx,
                    "instruction": inst,
                    "error": str(e)
                })
                logger.warning(f"[InstructionExecutor] instruction execution failed: {e}")

        # Validate data integrity
        is_complete, missing_fields = self.validate_completeness()

        return {
            "success": is_complete and len(failed_instructions) == 0,
            "data": self.data,
            "applied": self.stats["success"],
            "failed": self.stats["failed"],
            "errors": failed_instructions,
            "is_complete": is_complete,
            "missing_fields": missing_fields
        }

    def validate_completeness(self) -> tuple[bool, list[str]]:
        """
        Validate data integrity

        Returns:
            (is_complete, missing_fields):
            - is_complete: whether complete
            - missing_fields: list of missing required field paths
        """
        from app.services.ai.core.model_builder import build_model_from_json_schema

        try:
            # Validate using a Pydantic dynamic model
            DynamicModel = build_model_from_json_schema('ValidationModel', self.schema)
            DynamicModel(**self.data)
            return True, []
        except ValidationError as e:
            # Extract missing fields
            missing_fields = []
            for error in e.errors():
                if error.get('type') == 'missing':
                    loc = error.get('loc', ())
                    if loc:
                        path = '/' + '/'.join(str(l) for l in loc)
                        missing_fields.append(path)

            return False, missing_fields

    def get_data(self) -> Dict[str, Any]:
        """Get current data"""
        return self.data

    def get_stats(self) -> Dict[str, int]:
        """Get execution statistics"""
        return self.stats.copy()