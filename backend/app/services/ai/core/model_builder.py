"""Dynamic model builder service

Responsible for dynamically building Pydantic models from JSON Schema.
"""

from typing import Dict, Any, List, Type
from pydantic import create_model, Field as PydanticField, BaseModel
from typing import Any as _Any, Dict as _Dict, List as _List


def json_schema_to_py_type(sch: Dict[str, Any], schema_root: Dict[str, Any] = None) -> Any:
    """Convert a JSON Schema type to a Python type annotation

    Args:
        sch: JSON Schema definition
        schema_root: Root Schema (used to resolve $ref)

    Returns:
        Python type annotation or Pydantic model class
    """
    if not isinstance(sch, dict):
        return _Any

    # Handle $ref
    if '$ref' in sch:
        ref_path = sch['$ref']
        # Simple $ref resolution: #/$defs/ModelName
        if ref_path.startswith('#/$defs/') and schema_root and '$defs' in schema_root:
            def_name = ref_path.split('/')[-1]
            ref_schema = schema_root['$defs'].get(def_name)
            if ref_schema:
                # Recursively build the referenced model
                # Use the reference name as the model name to avoid hash-based naming
                return build_model_from_json_schema(def_name, ref_schema, schema_root)

        # Resolution failed or no definitions, fall back to Dict
        return _Dict[str, _Any]

    t = sch.get('type')

    if t == 'string':
        return str
    if t == 'integer':
        return int
    if t == 'number':
        return float
    if t == 'boolean':
        return bool
    if t == 'array':
        item_sch = sch.get('items') or {}
        return _List[json_schema_to_py_type(item_sch, schema_root)]  # type: ignore[index]
    if t == 'object':
        # **Key fix**: if there are properties, recursively build a nested Pydantic model
        if 'properties' in sch:
            # Generate a unique nested model name
            import hashlib
            schema_str = str(sorted(sch.get('properties', {}).keys()))
            model_hash = hashlib.md5(schema_str.encode()).hexdigest()[:8]
            nested_model_name = f'NestedModel_{model_hash}'
            return build_model_from_json_schema(nested_model_name, sch, schema_root)
        else:
            # Object without properties, treat as Dict
            return _Dict[str, _Any]

    # Type not declared or unrecognizable
    return _Any


def build_model_from_json_schema(model_name: str, schema: Dict[str, Any], root_schema: Dict[str, Any] = None) -> Type[BaseModel]:
    """Dynamically build a Pydantic model from JSON Schema

    Args:
        model_name: Model name
        schema: JSON Schema definition
        root_schema: Root Schema (used to resolve $ref), defaults to schema itself

    Returns:
        The dynamically created Pydantic model class
    """
    if root_schema is None:
        root_schema = schema

    # 1. If the current schema itself is a $ref, resolve it directly and return the referenced model
    if '$ref' in schema:
         return json_schema_to_py_type(schema, root_schema)

    props: Dict[str, Any] = (schema or {}).get('properties') or {}
    required: List[str] = list((schema or {}).get('required') or [])
    field_defs: Dict[str, tuple] = {}

    for fname, fsch in props.items():
        # Get the type annotation (may be a nested model)
        # Pass root_schema so definitions can still be found in deeply nested structures
        anno = json_schema_to_py_type(fsch if isinstance(fsch, dict) else {}, root_schema)

        # Get the description
        desc = fsch.get('description') if isinstance(fsch, dict) else None

        # Determine whether it is required
        is_required = fname in required

        # Build the field definition: required uses ..., optional uses None
        if desc is not None:
            default_val = PydanticField(... if is_required else None, description=desc)
        else:
            default_val = ... if is_required else None

        field_defs[fname] = (anno, default_val)

    return create_model(model_name, **field_defs)