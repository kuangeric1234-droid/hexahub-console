from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://hexa:secret@localhost:5432/hexa_hub"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # LLM providers
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # Storage (MinIO / S3-compatible)
    AWS_ACCESS_KEY_ID:     str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_ENDPOINT_URL:      str = "http://localhost:9000"
    S3_BUCKET_NAME:        str = "hexa-hub-assets"

    # Platform publishing (wire up per platform)
    LINKEDIN_ACCESS_TOKEN: str = ""
    LINKEDIN_PERSON_URN:   str = ""   # urn:li:person:{id}
    META_ACCESS_TOKEN:     str = ""
    META_IG_USER_ID:       str = ""
    WORDPRESS_URL:         str = ""   # e.g. https://blog.hexahub.com.au
    WORDPRESS_APP_PASSWORD: str = ""

    # Webhook for XHS / WeChat manual publishing packages
    WEBHOOK_URL: str = ""             # e.g. https://hooks.slack.com/... or n8n endpoint

    # App
    DEBUG: bool = False


settings = Settings()
