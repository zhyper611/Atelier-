from app.providers.ark_client import humanize_provider_error


def test_humanize_sensitive_content_error() -> None:
    message = humanize_provider_error(
        RuntimeError(
            "The request failed because the input text may contain sensitive information. "
            "Request id: 021779259008253"
        )
    )
    assert "内容安全" in message
    assert "Request id" not in message


def test_humanize_model_not_activated() -> None:
    message = humanize_provider_error(
        RuntimeError(
            "Your account has not activated the model doubao-seed-2-0-lite-260215. "
            "Please activate the model service in the Ark Console.",
        ),
    )
    assert "未开通" in message
    assert "ARK_CHAT_ENDPOINT_ID" in message or "接入点" in message


def test_humanize_generic_error() -> None:
    message = humanize_provider_error(RuntimeError("network down"))
    assert "network down" in message
