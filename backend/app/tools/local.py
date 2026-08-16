import ast
import operator
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings

MAX_EXPRESSION_LENGTH = 256
MAX_DEPTH = 20
MAX_ABS_EXPONENT = 100
MAX_ABS_RESULT = Decimal("1e100")


def current_time(timezone_name: str | None = None) -> dict[str, str]:
    """Return current local and UTC datetimes for a validated IANA timezone."""
    requested = timezone_name or get_settings().app_timezone
    try:
        zone = ZoneInfo(requested)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {requested}") from exc
    now_utc = datetime.now(UTC)
    return {
        "timezone": requested,
        "local_datetime": now_utc.astimezone(zone).isoformat(),
        "utc_datetime": now_utc.isoformat(),
    }


_BINARY: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[Decimal], Decimal]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(node: ast.AST, depth: int = 0) -> Decimal:
    if depth > MAX_DEPTH:
        raise ValueError("Expression nesting is too deep")
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate(node.operand, depth + 1))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left = _evaluate(node.left, depth + 1)
        right = _evaluate(node.right, depth + 1)
        if isinstance(node.op, ast.Pow):
            if right != right.to_integral_value() or abs(right) > MAX_ABS_EXPONENT:
                raise ValueError("Exponent must be an integer between -100 and 100")
        result = _BINARY[type(node.op)](left, right)
        if not result.is_finite() or abs(result) > MAX_ABS_RESULT:
            raise ValueError("Result is outside the supported range")
        return result
    raise ValueError("Only numeric literals, parentheses, and + - * / % ** are allowed")


def calculator(expression: str, precision: int = 28) -> dict[str, str | int]:
    """Safely evaluate bounded arithmetic without eval or arbitrary names/calls."""
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expression must contain 1 to 256 characters")
    if precision < 1 or precision > 50:
        raise ValueError("Precision must be between 1 and 50")
    try:
        tree = ast.parse(expression, mode="eval")
        with localcontext() as context:
            context.prec = precision
            result = _evaluate(tree)
    except (SyntaxError, InvalidOperation, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"Invalid arithmetic expression: {exc}") from exc
    normalized = format(result.normalize(), "f")
    if normalized == "-0":
        normalized = "0"
    return {"expression": expression, "result": normalized, "precision": precision}
