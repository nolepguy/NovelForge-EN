"""Expression validator (same rules as the execution engine)"""

from typing import List

from .evaluator import validate_expression_syntax


class ExpressionValidator:
    """Expression validator"""

    def validate(self, expression: str) -> List[str]:
        return validate_expression_syntax(expression)


def validate_expression(expression: str) -> List[str]:
    """Convenience function: validate an expression"""
    validator = ExpressionValidator()
    return validator.validate(expression)