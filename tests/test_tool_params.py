from app.agent.schemas import RequestOptions
from app.agent.tools.params import coalesce_duration, coalesce_size, extract_duration, extract_size


def test_extract_size_from_explicit_dimensions() -> None:
    assert extract_size("画一张 1024x768 的图", "1024x1024") == "1024x768"


def test_extract_size_from_16_9_ratio() -> None:
    options = RequestOptions(default_image_size="1024x1024")
    assert extract_size("16:9 赛博朋克城市", options.default_image_size) == "1024x576"


def test_extract_duration_from_message() -> None:
    assert extract_duration("生成 10 秒视频", 5) == 10


def test_coalesce_size_prefers_tool_argument() -> None:
    assert coalesce_size("2048x2048", "16:9 图片", "1024x1024") == "2048x2048"


def test_coalesce_duration_clamps_to_range() -> None:
    assert coalesce_duration(999, "5 秒视频", 5) == 120
