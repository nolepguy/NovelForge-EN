"""Expression node - data transformation and extraction"""

from __future__ import annotations

import inspect
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from app.services.workflow.expressions import evaluate_expression
from app.services.workflow.expressions.builtins import get_safe_builtins
from app.services.workflow.expressions.functions import get_builtin_functions, get_helper_metadata
from app.services.workflow.nodes.base import BaseNode
from app.services.workflow.registry import register_node


class ExpressionInput(BaseModel):
    """Expression node input"""

    expression: str = Field(
        ...,
        description="Python expression (can access all defined variables)",
        json_schema_extra={
            "x-component": "CodeEditor",
            "x-component-props": {
                "language": "python",
                "placeholder": "e.g.: card.content.field or []\n[item.name for item in items if item.name]"
            }
        },
    )


class ExpressionOutput(BaseModel):
    """Expression node output"""

    result: Any = Field(..., description="Expression evaluation result")


def _build_helper_docs() -> list[str]:
    helpers = get_builtin_functions()
    helper_meta = get_helper_metadata()
    if not helpers:
        return ["- (no business helpers)"]

    ranked_names = sorted(
        helpers.keys(),
        key=lambda name: (helper_meta.get(name).priority if helper_meta.get(name) else 50, name),
        reverse=True,
    )

    lines: list[str] = ["### Recommended helpers (by priority)"]
    for name in ranked_names[:3]:
        func = helpers[name]
        signature = str(inspect.signature(func))
        meta = helper_meta.get(name)
        summary = (meta.summary if meta else ((inspect.getdoc(func) or "").splitlines()[0] if inspect.getdoc(func) else "Business helper function")).strip()
        scenario = meta.scenario if meta else "general"
        example = meta.example if meta else ""
        line = f"- `{name}{signature}` (scenario: {scenario}, priority: {meta.priority if meta else 50})\n  - Description: {summary}"
        if example:
            line += f"\n  - Example: `{example}`"
        lines.append(line)

    lines.append("\n### Full helper list")
    for name in ranked_names:
        func = helpers[name]
        signature = str(inspect.signature(func))
        meta = helper_meta.get(name)
        summary = (meta.summary if meta else ((inspect.getdoc(func) or "").splitlines()[0] if inspect.getdoc(func) else "Business helper function")).strip()
        lines.append(f"- `{name}{signature}`: {summary}")
    return lines


def _build_builtin_docs() -> str:
    builtin_names = sorted(get_safe_builtins().keys())
    return ", ".join(f"`{name}`" for name in builtin_names)


def _build_expression_documentation() -> str:
    helper_lines = "\n".join(_build_helper_docs())
    builtin_line = _build_builtin_docs()

    return f"""
The expression node executes **controlled Python expressions**, suitable for field
extraction, list transformation, and conditional assembly.

## Core rules (AI must read)
1. The node output structure is fixed as `{{"result": <evaluation result>}}`; later
   nodes must access it via `.result`.
2. Workflow context variables (e.g. `project`, `cards`, `wait_xxx`) can be accessed
   directly.
3. Prefer standard Python expression syntax (comprehensions, ternary expressions,
   f-strings).
4. Dicts support attribute access (e.g. `card.content.title`); missing fields are
   treated as empty values.

## Recommended patterns
```python
card.content.items or []
[item for item in items if item.status == "active"]
f"Processed {{len(items)}} items"
items if wait_ai.count > 0 else []
```

## Output access example
```python
mapped = Logic.Expression(expression="{{item.id: item.name for item in cards}}")
Card.BatchUpsert(items=mapped.result)
```

## Available Python builtins
{builtin_line}

## Business helpers (auto-generated)
{helper_lines}
""".strip()


@register_node
class ExpressionNode(BaseNode):
    """Expression node (controlled Python eval)"""

    node_type = "Logic.Expression"
    category = "logic"
    label = "Expression Evaluation"
    description = "Execute a controlled Python expression, output result"

    input_model = ExpressionInput
    output_model = ExpressionOutput

    @classmethod
    def get_metadata(cls):
        metadata = super().get_metadata()
        metadata.description = cls.description
        metadata.documentation = _build_expression_documentation()
        return metadata

    async def execute(self, input_data: ExpressionInput) -> AsyncIterator[ExpressionOutput]:
        """Execute the expression"""
        expr_context = self.context.variables

        try:
            result = evaluate_expression(input_data.expression, expr_context)
            yield ExpressionOutput(result=result)
        except Exception as e:
            raise ValueError(
                f"Expression execution failed: {str(e)}\n"
                f"Expression: {input_data.expression}\n"
                f"Available variables: {', '.join(expr_context.keys())}"
            )