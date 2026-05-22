import pytest

from app.agent.tools.code_runner import CodeSafetyError, run_python_code, validate_python_code


def test_validate_rejects_import() -> None:
    with pytest.raises(CodeSafetyError):
        validate_python_code("import os\nprint(1)")


@pytest.mark.asyncio
async def test_run_python_prints_output() -> None:
    stdout, stderr = await run_python_code(
        "print(2 + 2)",
        timeout_seconds=5.0,
        max_output_chars=1000,
    )
    assert "4" in stdout
    assert stderr is None


@pytest.mark.asyncio
async def test_run_python_timeout() -> None:
    with pytest.raises(TimeoutError):
        await run_python_code(
            "while True:\n    pass",
            timeout_seconds=0.2,
            max_output_chars=1000,
        )
