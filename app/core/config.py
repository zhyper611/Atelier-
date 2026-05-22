from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI AI Agent"
    agent_display_name: str = "Atelier 智能助手"
    agent_identity_mask_doubao: bool = True
    default_session_id: str = "default"

    volc_access_key_id: str | None = None
    volc_secret_access_key: str | None = None
    volc_region: str = "cn-beijing"
    ark_api_key: str | None = None

    llm_api_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "doubao-seed-2-0-lite-260215"
    # 方舟「推理接入点」ID（ep- 开头），若已创建接入点则优先于 LLM_MODEL
    ark_chat_endpoint_id: str | None = None
    # 识图专用；不填则与 LLM_MODEL 相同（火山 Doubao-Seed-2.0-lite 等多模态模型）
    vision_model: str | None = None
    # 将图片/音视频以 data URL 内联进 user 消息（需多模态模型，如 Doubao-Seed-2.0-lite）
    multimodal_inline_attachments: bool = True
    multimodal_inline_max_bytes: int = Field(default=4_194_304, ge=1024)
    search_api_base_url: str | None = None
    search_api_aksk_url: str | None = None
    search_api_method: str = "POST"
    search_api_content_type: str = "application/json"
    search_api_key: str | None = None
    search_api_auth_scheme: str = "Bearer"
    search_result_count: int = Field(default=5, ge=1, le=20)
    image_api_base_url: str | None = None
    image_api_key: str | None = None
    image_response_format: str = "url"
    image_watermark: bool = True
    video_api_base_url: str | None = None
    video_tasks_url: str | None = None
    video_task_status_url_template: str | None = None
    video_api_key: str | None = None
    image_model: str = "seedream-4.5"
    video_model: str = "seedance-1.0"
    video_ratio: str = "16:9"
    video_resolution: str = "720p"
    video_watermark: bool = True
    video_poll_interval_seconds: int = Field(default=10, ge=1)
    video_poll_timeout_seconds: int = Field(default=600, ge=1)

    default_image_size: str = Field(default="1024x1024")
    default_video_size: str = Field(default="1280x720")
    default_video_duration_seconds: int = Field(default=5)
    use_mock_providers: bool = False
    agent_max_steps: int = Field(default=10, ge=1, le=20)
    final_tool_context_max_chars: int = Field(default=12000, ge=2000)
    enable_agent_planning: bool = True
    planning_min_message_chars: int = Field(default=60, ge=0)
    attachments_dir: str = "data/attachments"
    attachment_max_bytes: int = Field(default=5_242_880, ge=1024)
    session_store: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://127.0.0.1:6379/0"
    session_ttl_seconds: int = Field(default=0, ge=0)
    trace_observation_max_chars: int = Field(default=4000, ge=500)

    fetch_url_enabled: bool = True
    fetch_url_timeout_seconds: int = Field(default=15, ge=1)
    fetch_url_max_bytes: int = Field(default=2_097_152, ge=1024)
    fetch_url_max_content_chars: int = Field(default=12000, ge=500)
    fetch_url_max_urls_per_call: int = Field(default=3, ge=1, le=10)
    fetch_url_max_redirects: int = Field(default=5, ge=0, le=20)
    fetch_url_blocked_domains: str = (
        "localhost,127.0.0.1,0.0.0.0,::1,"
        "metadata.google.internal,metadata.internal"
    )
    fetch_url_user_agent: str = (
        "Mozilla/5.0 (compatible; AtelierAgent/1.0; +https://example.com/bot)"
    )

    api_key: str | None = None
    auth_enabled: bool = True
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = Field(default=1440, ge=1)
    users_db_path: str = "data/users.db"
    auth_bypass_user_id: str = "test-user"
    rate_limit_requests: int = Field(default=30, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    tool_timeout_seconds: int = Field(default=120, ge=1)
    video_tool_timeout_seconds: int = Field(default=600, ge=1)
    tool_retry_max_attempts: int = Field(default=2, ge=1, le=5)
    llm_timeout_seconds: int = Field(default=120, ge=1)
    enable_structured_logs: bool = True

    knowledge_enabled: bool = True
    knowledge_redis_url: str | None = None
    embedding_api_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str = "doubao-embedding-vision-251215"
    embedding_dimensions: int = Field(default=2048, ge=64, le=4096)
    knowledge_chunk_size: int = Field(default=800, ge=100)
    knowledge_chunk_overlap: int = Field(default=150, ge=0)
    knowledge_top_k: int = Field(default=5, ge=1, le=20)
    knowledge_auto_retrieve: bool = True
    knowledge_index_name: str = "agent_kb"
    knowledge_excerpt_max_chars: int = Field(default=400, ge=50)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def resolved_knowledge_redis_url(self) -> str:
        return self.knowledge_redis_url or self.redis_url

    def resolved_embedding_api_base_url(self) -> str | None:
        return self.embedding_api_base_url or self.llm_api_base_url

    def resolved_embedding_api_key(self) -> str | None:
        return self.embedding_api_key or self.llm_api_key or self.ark_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
