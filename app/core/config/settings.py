"""应用配置模块 — 所有环境变量通过 pydantic-settings 管理."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env 文件和环境变量加载."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- 应用 ---
    APP_ENV: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_VERSION: str = "0.1.0"

    # --- 数据库 ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/safe_launch"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20

    # --- DeepSeek LLM ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT: int = 60
    DEEPSEEK_MAX_RETRIES: int = 1

    # --- Qdrant 向量数据库 ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "game_regulations"

    # --- Embedding (OpenAI / Ollama 兼容) ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "http://localhost:11434/v1"
    OPENAI_EMBEDDING_MODEL: str = "qwen3-embedding:0.6b"

    # --- 图片审核私有服务 ---
    IMAGE_REVIEW_API_URL: str | None = None
    IMAGE_REVIEW_API_KEY: str | None = None
    IMAGE_REVIEW_TIMEOUT: int = 30

    # --- 审核业务配置 ---
    BATCH_MAX_SIZE: int = 100
    BATCH_CONCURRENCY: int = 5
    L1_KEYWORD_DIR: str = "data/keywords"
    L2_RAG_TOP_K: int = 5


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例."""
    return Settings()


# 模块级单例，方便直接导入
settings = get_settings()
