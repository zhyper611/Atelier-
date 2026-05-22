from __future__ import annotations

import math
import re

# Seedream 4.5 minimum total pixels (e.g. 1920x1920).
ARK_MIN_IMAGE_PIXELS = 3_686_400

_SIZE_PATTERN = re.compile(r"^(?P<width>\d{3,5})\s*[xX*×]\s*(?P<height>\d{3,5})$")


def parse_image_dimensions(size: str) -> tuple[int, int]:
    normalized = size.strip()
    if normalized.upper() in {"2K", "4K"}:
        return (2048, 2048) if normalized.upper() == "2K" else (4096, 4096)

    match = _SIZE_PATTERN.match(normalized)
    if match is None:
        return 2048, 2048

    width = int(match.group("width"))
    height = int(match.group("height"))
    if width <= 0 or height <= 0:
        return 2048, 2048
    return width, height


def normalize_image_size(size: str, min_pixels: int = ARK_MIN_IMAGE_PIXELS) -> str:
    width, height = parse_image_dimensions(size)
    pixels = width * height
    if pixels >= min_pixels:
        return f"{width}x{height}"

    scale = math.sqrt(min_pixels / pixels)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))

    while new_width * new_height < min_pixels:
        new_width += 1

    return f"{new_width}x{new_height}"
