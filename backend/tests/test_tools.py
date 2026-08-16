from datetime import datetime

import pytest

from app.tools.local import calculator, current_time


def test_calculator_respects_precedence_and_decimals() -> None:
    assert calculator("2 + 3 * 4")["result"] == "14"
    assert calculator("0.1 + 0.2")["result"] == "0.3"
    assert calculator("2 ** 8")["result"] == "256"


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "open('/etc/passwd')",
        "value + 1",
        "(1).__class__",
        "2 ** 1000",
        "1 / 0",
    ],
)
def test_calculator_rejects_unsafe_or_unbounded_input(expression: str) -> None:
    with pytest.raises(ValueError):
        calculator(expression)


def test_current_time_uses_valid_timezone() -> None:
    result = current_time("America/Los_Angeles")
    assert result["timezone"] == "America/Los_Angeles"
    assert datetime.fromisoformat(result["local_datetime"]).utcoffset() is not None
    assert datetime.fromisoformat(result["utc_datetime"]).utcoffset() is not None


def test_current_time_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        current_time("Mars/Olympus_Mons")
