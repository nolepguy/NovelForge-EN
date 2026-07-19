"""Workflow DSL parser (comment-marker DSL).

Only supports the following node block format:
1) Comment-marker node blocks (the only supported format)
   #@node(async=true, disabled=false, description="...")
   var_name = Category.NodeType(...)
   #</node>

Does not support the XML node format (<node ...>...</node>).
"""

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..engine.execution_plan import ExecutionPlan, Statement
from ..expressions.builtins import get_safe_global_names


class WorkflowParser:
    """Workflow parser (comment-marker DSL)."""

    _RE_NODE_OPEN = re.compile(r"^\s*#@node(?:\((.*)\))?\s*$")
    _RE_NODE_CLOSE = re.compile(r"^\s*#</node>\s*$")

    def parse(self, code: str) -> ExecutionPlan:
        """Parse workflow code."""
        if not code or not code.strip():
            return ExecutionPlan(statements=[], dependencies={})

        # Tolerate UTF-8 BOM to avoid the first-line marker being misjudged
        code = code.lstrip("\ufeff")

        if self._looks_like_xml(code):
            raise ValueError("XML workflow format is no longer supported. Please use the #@node(...) ... #</node> comment-marker DSL.")

        if not self._looks_like_marker_dsl(code):
            raise ValueError("Workflow code must use the #@node(...) ... #</node> comment-marker DSL.")

        statements = self._parse_marker_dsl(code)
        dependencies = {stmt.variable: stmt.depends_on for stmt in statements}
        plan = ExecutionPlan(statements=statements, dependencies=dependencies)
        plan.validate()

        logger.debug(f"[WorkflowParser] Parsed successfully, mode=marker, node count={len(statements)}")
        return plan

    def _looks_like_xml(self, code: str) -> bool:
        return bool(re.search(r"<\s*node\b", code))

    def _looks_like_marker_dsl(self, code: str) -> bool:
        return bool(re.search(r"^\s*#@node(?:\(|\s*$)", code, re.MULTILINE))

    def _parse_marker_dsl(self, code: str) -> List[Statement]:
        lines = code.splitlines()
        statements: List[Statement] = []
        index = 0

        while index < len(lines):
            line = lines[index]
            match = self._RE_NODE_OPEN.match(line)
            if not match:
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    index += 1
                    continue

                raise ValueError(
                    f"Line {index + 1} contains code not wrapped in a node block. Please wrap nodes with #@node(...) and #</node>."
                )

            meta = self._parse_node_meta(match.group(1) or "")
            open_line_no = index + 1
            index += 1

            block_lines: List[str] = []
            while index < len(lines) and not self._RE_NODE_CLOSE.match(lines[index]):
                block_lines.append(lines[index])
                index += 1

            if index >= len(lines):
                raise ValueError(f"Node metadata (line {open_line_no}) is missing the closing '#</node>' marker")

            index += 1
            code_block = "\n".join(block_lines)
            if not code_block:
                raise ValueError(f"No node code after node metadata (line {open_line_no})")

            stmt = self._parse_python_node_block(
                code_block=code_block,
                line_number=open_line_no,
                fallback_name=meta.get("name"),
                is_async=bool(meta.get("is_async", False)),
                disabled=bool(meta.get("disabled", False)),
                description=str(meta.get("description", "") or ""),
            )
            statements.append(stmt)

        return statements

    def _parse_node_meta(self, meta_text: str) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "is_async": False,
            "disabled": False,
            "description": "",
            "name": None,
        }

        content = (meta_text or "").strip()
        if not content:
            return meta

        parts = self._split_meta_pairs(content)
        for part in parts:
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"Invalid node metadata fragment: '{part}' (expected key=value)")

            key, raw_value = part.split("=", 1)
            key = key.strip()
            value = self._parse_meta_value(raw_value.strip())

            if key in ("async", "is_async"):
                meta["is_async"] = self._to_bool(value, field_name=key)
            elif key == "disabled":
                meta["disabled"] = self._to_bool(value, field_name=key)
            elif key == "description":
                meta["description"] = str(value)
            elif key == "name":
                meta["name"] = str(value)
            else:
                raise ValueError(f"Unsupported node metadata key: '{key}'")

        return meta

    def _split_meta_pairs(self, text: str) -> List[str]:
        result: List[str] = []
        buffer: List[str] = []
        quote: Optional[str] = None
        escaped = False
        depth = 0

        for char in text:
            if quote is not None:
                buffer.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue

            if char in ('"', "'"):
                quote = char
                buffer.append(char)
                continue

            if char in "([{" :
                depth += 1
                buffer.append(char)
                continue

            if char in ")]}":
                depth = max(0, depth - 1)
                buffer.append(char)
                continue

            if char == "," and depth == 0:
                result.append("".join(buffer).strip())
                buffer = []
                continue

            buffer.append(char)

        if quote is not None:
            raise ValueError("Node metadata quote is not closed")

        tail = "".join(buffer).strip()
        if tail:
            result.append(tail)
        return result

    def _parse_meta_value(self, raw: str) -> Any:
        lowered = raw.lower()
        if lowered in ("true", "yes", "on"):
            return True
        if lowered in ("false", "no", "off"):
            return False
        if raw == "1":
            return True
        if raw == "0":
            return False

        try:
            return ast.literal_eval(raw)
        except Exception:
            return raw

    def _to_bool(self, value: Any, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes", "on"):
                return True
            if lowered in ("false", "0", "no", "off"):
                return False
        raise ValueError(f"Node metadata field '{field_name}' expects a boolean, got: {value}")

    def _parse_python_node_block(
        self,
        code_block: str,
        line_number: int,
        fallback_name: Optional[str],
        is_async: bool,
        disabled: bool,
        description: str,
    ) -> Statement:
        normalized_block = self._strip_non_meta_comments(code_block)
        try:
            tree = ast.parse(normalized_block)
        except SyntaxError as e:
            raise ValueError(f"Node code syntax error: {e}")

        if len(tree.body) != 1:
            raise ValueError("Each node block must contain exactly one statement (a single assignment statement is recommended)")

        node = tree.body[0]
        variable: Optional[str] = None
        call_node: Optional[ast.Call] = None

        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise ValueError("Node assignment statement must be a simple variable assignment, e.g. a = Logic.Expression(...)")
            variable = node.targets[0].id
            if not isinstance(node.value, ast.Call):
                raise ValueError("The right-hand side of a node assignment must be a node call, e.g. Logic.Expression(...)")
            call_node = node.value
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if not fallback_name:
                raise ValueError("When a node block is a call without assignment, provide name=... metadata in #@node(...)")
            variable = fallback_name
            call_node = node.value
        else:
            raise ValueError("Node blocks only support call expressions or assignment call expressions")

        call_expr = ast.unparse(call_node)
        node_type, config = self._parse_node_call(call_expr)
        depends_on = self._extract_dependencies(call_expr, node_type)

        stmt = Statement(
            line_number=line_number,
            variable=variable,
            node_type=node_type,
            config=config,
            is_async=is_async,
            depends_on=depends_on,
            code=call_expr,
            disabled=disabled,
            description=description,
        )

        logger.debug(
            f"[WorkflowParser/Marker] Node: {variable}, type: {node_type}, "
            f"async: {is_async}, disabled: {disabled}, description: {description}"
        )
        return stmt

    def _strip_non_meta_comments(self, code_block: str) -> str:
        kept_lines: List[str] = []
        for raw_line in code_block.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            kept_lines.append(raw_line)
        return "\n".join(kept_lines).strip()

    def _parse_node_call(self, call_expr: str) -> Tuple[str, Dict[str, Any]]:
        try:
            tree = ast.parse(call_expr, mode="eval")
            expr = tree.body

            if not isinstance(expr, ast.Call):
                raise ValueError("Not a valid node call")

            if isinstance(expr.func, ast.Attribute):
                if isinstance(expr.func.value, ast.Name):
                    category = expr.func.value.id
                    method = expr.func.attr
                    node_type = f"{category}.{method}"
                elif isinstance(expr.func.value, ast.Attribute):
                    parts = []
                    node = expr.func
                    while isinstance(node, ast.Attribute):
                        parts.insert(0, node.attr)
                        node = node.value
                    if isinstance(node, ast.Name):
                        parts.insert(0, node.id)
                    node_type = ".".join(parts)
                else:
                    raise ValueError("Unsupported node type format")
            else:
                raise ValueError("Node call must be in NodeType.Method(...) format")

            config = {}
            for keyword in expr.keywords:
                key = keyword.arg
                value = self._parse_value(keyword.value)
                config[key] = value

            return node_type, config
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {e}")
        except Exception as e:
            raise ValueError(f"Parse failed: {e}")

    def _parse_value(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return f"${node.id}"
        if isinstance(node, ast.Attribute):
            obj = self._parse_value(node.value)
            return f"{obj}.{node.attr}"
        if isinstance(node, ast.List):
            return [self._parse_value(elt) for elt in node.elts]
        if isinstance(node, ast.Dict):
            return {self._parse_value(k): self._parse_value(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, (ast.ListComp, ast.DictComp)):
            return f"${{{ast.unparse(node)}}}"
        return f"${{{ast.unparse(node)}}}"

    def _extract_dependencies(self, expr: str, exclude_node_type: Optional[str] = None) -> List[str]:
        try:
            tree = ast.parse(expr, mode="eval")
        except Exception:
            return []

        dependencies = set()
        exclude_parts = set(exclude_node_type.split(".")) if exclude_node_type else set()
        safe_names = get_safe_global_names()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if (
                    node.id not in ["True", "False", "None"]
                    and node.id not in exclude_parts
                    and node.id not in safe_names
                ):
                    dependencies.add(node.id)
            elif isinstance(node, ast.Attribute):
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value
                if (
                    isinstance(root, ast.Name)
                    and root.id not in exclude_parts
                    and root.id not in safe_names
                ):
                    dependencies.add(root.id)

        return sorted(list(dependencies))


def parse_workflow(code: str) -> ExecutionPlan:
    """Convenience function: parse workflow code."""
    parser = WorkflowParser()
    return parser.parse(code)