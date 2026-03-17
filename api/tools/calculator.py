"""
Calculator Tool — Safe mathematical expression evaluation.
"""
import ast
import operator
import logging
from api.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Safe operators whitelist
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = "Evaluate mathematical expressions safely. Input: math expression string."

    async def execute(self, expression: str, **kwargs) -> str:
        """Safely evaluate a math expression using AST."""
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = self._eval_node(tree.body)
            return f"{expression.strip()} = {result}"
        except Exception as e:
            return f"Calculator error: {str(e)}"

    def _eval_node(self, node):
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return SAFE_OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            operand = self._eval_node(node.operand)
            return SAFE_OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")
