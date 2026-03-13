from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    BOT_TOKEN: str
    ADMIN_TELEGRAM_ID: int

    # Google AI Studio
    GEMINI_API_KEY: str
    LLM_LITE_MODEL: str
    LLM_ADVANCED_MODEL: str

    # OpenRouter (embeddings)
    OPENROUTER_API_KEY: str
    EMBED_MODEL: str

    # Jina AI (reranking)
    JINA_API_KEY: str
    RERANKER_MODEL: str

    # Cloudflare R2
    CF_R2_ENDPOINT: str
    CF_R2_ACCESS_KEY_ID: str
    CF_R2_SECRET_ACCESS_KEY: str
    CF_R2_BUCKET: str
    CF_R2_PUBLIC_BASE_URL: str

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Application
    APP_BASE_URL: str
    ENVIRONMENT: str = "development"
    WEBHOOK_SECRET: str = ""  # Required in production; empty string disables check in dev

    # RAG Thresholds
    RETRIEVAL_SCORE_THRESHOLD: float = 0.65
    RETRIEVAL_NO_ANSWER_THRESHOLD: float = 0.30

    # Embedding dimension — pgvector HNSW max = 2000; qwen3-embedding-4b supports MRL truncation
    # Confirm actual dim from first OpenRouter call; update .env before applying migration
    EMBED_DIM: int = 1024


settings = Settings()
