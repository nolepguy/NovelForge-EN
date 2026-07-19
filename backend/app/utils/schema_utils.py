"""Schema processing utilities

Used for filtering and transforming JSON Schema.
"""

from typing import Any, Dict, List
from copy import deepcopy


def filter_schema_for_ai(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Metadata-based schema filtering (removes fields marked x-ai-exclude=true)
    
    Args:
        schema: JSON Schema object
        
    Returns:
        The filtered schema
    """
    def prune(node: Any, parent_required: List[str] | None = None) -> Any:
        if isinstance(node, dict):
            # Object: filter fields in properties marked with x-ai-exclude
            if node.get('type') == 'object' and isinstance(node.get('properties'), dict):
                props = node.get('properties') or {}
                required = list(node.get('required') or [])
                new_props: Dict[str, Any] = {}
                for name, sch in props.items():
                    if isinstance(sch, dict) and sch.get('x-ai-exclude') is True:
                        # Remove from required
                        if name in required:
                            required = [r for r in required if r != name]
                        continue
                    new_props[name] = prune(sch)
                node = dict(node)  # Copy
                node['properties'] = new_props
                if required:
                    node['required'] = required
                elif 'required' in node:
                    # If all removed, drop the required field
                    node.pop('required', None)
            # Array: recursively process items/prefixItems (tuple)
            if node.get('type') == 'array':
                if 'items' in node:
                    node = dict(node)
                    node['items'] = prune(node['items'])
                if 'prefixItems' in node and isinstance(node.get('prefixItems'), list):
                    node = dict(node)
                    node['prefixItems'] = [prune(it) for it in node.get('prefixItems', [])]
            # Composition keywords: recursively process anyOf/oneOf/allOf
            for kw in ('anyOf', 'oneOf', 'allOf'):
                if isinstance(node.get(kw), list):
                    node = dict(node)
                    node[kw] = [prune(it) for it in node.get(kw, [])]
            # $defs: only recurse into internal definitions (do not delete the defs key itself)
            if isinstance(node.get('$defs'), dict):
                defs = node.get('$defs') or {}
                new_defs: Dict[str, Any] = {}
                for k, v in defs.items():
                    new_defs[k] = prune(v)
                node = dict(node)
                node['$defs'] = new_defs
            # Clean up metadata traces (optional, not enforced)
            if 'x-ai-exclude' in node:
                node = dict(node)
                node.pop('x-ai-exclude', None)
            return node
        elif isinstance(node, list):
            return [prune(it) for it in node]
        return node

    try:
        root = deepcopy(schema) if isinstance(schema, dict) else {}
        return prune(root)
    except Exception:
        # On error, do not block the flow; fall back to the original schema
        return schema
