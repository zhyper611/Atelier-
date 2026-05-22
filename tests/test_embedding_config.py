from app.core.config import Settings
from app.knowledge.embeddings import (
    VolcengineMultimodalEmbeddingProvider,
    build_embedding_provider,
)


def test_default_embedding_model_is_doubao_vision() -> None:
    settings = Settings()
    assert settings.embedding_model == "doubao-embedding-vision-251215"
    assert settings.embedding_dimensions == 2048


def test_build_provider_uses_multimodal_for_vision_model() -> None:
    settings = Settings(
        use_mock_providers=False,
        embedding_model="doubao-embedding-vision-251215",
        llm_api_base_url="https://ark.cn-beijing.volces.com/api/v3",
        ark_api_key="ark-test",
    )
    provider = build_embedding_provider(settings)
    assert isinstance(provider, VolcengineMultimodalEmbeddingProvider)


def test_resolved_embedding_api_key_falls_back_to_ark() -> None:
    settings = Settings(
        embedding_api_key=None,
        llm_api_key=None,
        ark_api_key="ark-test-key",
    )
    assert settings.resolved_embedding_api_key() == "ark-test-key"
