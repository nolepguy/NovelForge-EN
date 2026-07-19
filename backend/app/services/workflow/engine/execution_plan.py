"""Execution plan

Represents the workflow execution plan, containing the statement list,
dependencies, and parallel groups.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any


@dataclass
class Statement:
    """A single statement (a node call or expression)"""
    line_number: int
    variable: str              # Variable name
    node_type: Optional[str]   # Node type (e.g. "Novel.Load"); None means a pure expression
    config: Dict[str, Any]     # Node configuration
    is_async: bool             # Whether to execute asynchronously
    depends_on: List[str]      # List of dependent variables
    code: Optional[str] = None # Original code
    disabled: bool = False     # Whether disabled (extracted from metadata comments)
    description: str = ""      # Node description (from #@node(description=...) metadata)

    def __repr__(self):
        return f"Statement(line={self.line_number}, var={self.variable}, type={self.node_type}, disabled={self.disabled})"


@dataclass
class ExecutionPlan:
    """Execution plan"""
    statements: List[Statement]           # Statement list (in code order)
    dependencies: Dict[str, List[str]]    # Dependencies: variable -> list of dependent variables

    def get_parallel_groups(self) -> List[List[Statement]]:
        """Get groups of statements that can run in parallel

        Design principles:
        1. Default sequential execution: one group per statement
        2. async nodes: marked as async but return immediately, not blocking subsequent statements
        3. wait statements: wait for previous async nodes to complete

        Returns: [[stmt1], [stmt2], [stmt3]]
        Meaning: execute each statement in order
        """
        # Simplified implementation: one group per statement, executed in order
        # async and wait handling is implemented in AsyncExecutor
        groups = [[stmt] for stmt in self.statements]
        return groups

    def _can_merge_with_last_group(
        self,
        last_group: List[Statement],
        new_stmts: List[Statement]
    ) -> bool:
        """Check whether new statements can run in parallel with the previous group

        Condition: the new statements do not depend on any variable in the previous group
        """
        last_group_vars = {stmt.variable for stmt in last_group}

        for new_stmt in new_stmts:
            # If a new statement depends on a variable in the previous group, it cannot run in parallel
            if any(dep in last_group_vars for dep in new_stmt.depends_on):
                return False

        return True

    def validate(self) -> None:
        """Validate the correctness of the execution plan

        Checks:
        1. All dependent variables are defined
        2. No circular dependencies
        """
        defined_vars = set()

        for stmt in self.statements:
            # Check dependencies
            for dep in stmt.depends_on:
                if dep not in defined_vars:
                    raise ValueError(
                        f"Line {stmt.line_number}: variable '{stmt.variable}' "
                        f"depends on undefined variable '{dep}'"
                    )

            # Add to the defined set
            defined_vars.add(stmt.variable)

        # Try to get parallel groups (detects circular dependencies)
        try:
            self.get_parallel_groups()
        except ValueError as e:
            raise ValueError(f"Execution plan validation failed: {e}")