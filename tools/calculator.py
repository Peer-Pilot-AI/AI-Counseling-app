import ast
import operator as op

TOOL = {
    "name": "calculator",
    "description": "Evaluate an arithmetic expression exactly (+ - * / // % **, parentheses). Use for any maths instead of guessing.",
    "parameters": {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. '(12.5 * 4) / 3'"}},
        "required": ["expression"],
    },
}

_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow,
        ast.USub: op.neg, ast.UAdd: op.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def run(arguments: dict) -> str:
    expr = arguments.get("expression", "")
    return str(_eval(ast.parse(expr, mode="eval").body))