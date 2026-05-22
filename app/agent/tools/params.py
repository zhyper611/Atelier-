from __future__ import annotations

import re

SIZE_PATTERN = re.compile(r"(?P<width>\d{3,5})\s*[xX*×]\s*(?P<height>\d{3,5})")
RATIO_PATTERN = re.compile(r"(?P<width>\d{1,2})\s*[:：/]\s*(?P<height>\d{1,2})")
DURATION_PATTERN = re.compile(r"(?P<duration>\d{1,3})\s*(秒|s|S)")


def extract_size(message: str, default_size: str) -> str:
    match = SIZE_PATTERN.search(message)
    if match is not None:
        return f"{match.group('width')}x{match.group('height')}"

    ratio_match = RATIO_PATTERN.search(message)
    if ratio_match is not None:
        ratio_width = int(ratio_match.group("width"))
        ratio_height = int(ratio_match.group("height"))
        if ratio_width > 0 and ratio_height > 0:
            base_width, _ = _parse_size_pair(default_size)
            computed_height = max(1, round(base_width * ratio_height / ratio_width))
            return f"{base_width}x{computed_height}"

    return default_size


def extract_duration(message: str, default_duration: int) -> int:
    match = DURATION_PATTERN.search(message)
    if match is None:
        return default_duration
    return max(1, min(int(match.group("duration")), 120))


def _parse_size_pair(size: str) -> tuple[int, int]:
    match = SIZE_PATTERN.fullmatch(size.strip())
    if match is None:
        return 2048, 2048
    return int(match.group("width")), int(match.group("height"))


def coalesce_size(size: object | None, message: str, default_size: str) -> str:
    if isinstance(size, str) and SIZE_PATTERN.search(size.replace("*", "x")):
        return extract_size(size, default_size)
    return extract_size(message, default_size)


def coalesce_duration(
    duration: object | None,
    message: str,
    default_duration: int,
) -> int:
    if isinstance(duration, int):
        return max(1, min(duration, 120))
    if isinstance(duration, float):
        return max(1, min(int(duration), 120))
    if isinstance(duration, str) and duration.isdigit():
        return max(1, min(int(duration), 120))
    return extract_duration(message, default_duration)
