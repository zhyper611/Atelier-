from app.providers.image_size import ARK_MIN_IMAGE_PIXELS, normalize_image_size, parse_image_dimensions


def test_parse_image_dimensions_supports_aliases() -> None:
    assert parse_image_dimensions("2K") == (2048, 2048)
    assert parse_image_dimensions("1024x576") == (1024, 576)


def test_normalize_image_size_scales_up_small_16_9() -> None:
    normalized = normalize_image_size("1024x576")

    width, height = parse_image_dimensions(normalized)
    assert width * height >= ARK_MIN_IMAGE_PIXELS
    assert normalized == "2560x1440"


def test_normalize_image_size_keeps_large_sizes() -> None:
    assert normalize_image_size("2048x2048") == "2048x2048"
