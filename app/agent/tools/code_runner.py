from __future__ import annotations

import ast
import asyncio
import sys
from typing import Any

_FORBIDDEN_NAMES = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
        "license",
        "copyright",
        "credits",
    },
)
_FORBIDDEN_MODULES = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "importlib",
        "ctypes",
        "multiprocessing",
        "threading",
        "signal",
        "pickle",
        "builtins",
    },
)


class CodeSafetyError(ValueError):
    pass


def validate_python_code(code: str) -> None:
    stripped = code.strip()
    if not stripped:
        raise CodeSafetyError("Empty code")
    try:
        tree = ast.parse(stripped)
    except SyntaxError as exc:
        raise CodeSafetyError(f"Syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CodeSafetyError("Imports are not allowed")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_NAMES:
                raise CodeSafetyError(f"Forbidden call: {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_NAMES:
                raise CodeSafetyError(f"Forbidden call: {func.attr}")
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_NAMES:
            raise CodeSafetyError(f"Forbidden attribute: {node.attr}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            if isinstance(getattr(node, "ctx", None), ast.Load):
                raise CodeSafetyError(f"Forbidden name: {node.id}")


async def run_python_code(
    code: str,
    *,
    timeout_seconds: float,
    max_output_chars: int,
) -> tuple[str, str | None]:
    validate_python_code(code)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"Execution exceeded {timeout_seconds}s")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if len(stdout) > max_output_chars:
        stdout = stdout[: max_output_chars - 3] + "..."
    if len(stderr) > max_output_chars:
        stderr = stderr[: max_output_chars - 3] + "..."
    return stdout, stderr if stderr.strip() else None
