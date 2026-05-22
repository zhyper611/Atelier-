import pytest

from app.agent.tools.calculator import safe_evaluate


def test_safe_evaluate_basic() -> None:
    assert safe_evaluate("(12 + 3) * 2") == 30.0


def test_safe_evaluate_rejects_names() -> None:
    with pytest.raises(ValueError):
        safe_evaluate("__import__('os')")
