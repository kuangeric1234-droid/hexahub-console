from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://hexa:secret@localhost:5432/hexa_hub"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth — legacy single-password (kept for backward compat)
    SECRET_KEY:                  str = "changeme"
    ALGORITHM:                   str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    API_PASSWORD:                str = "changeme"

    # Auth — JWT (preferred; falls back to SECRET_KEY / ALGORITHM if blank)
    JWT_SECRET_KEY:   str = ""         # if empty, falls back to SECRET_KEY
    JWT_ALGORITHM:    str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # CORS — comma-separated origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Webhooks
    WEBHOOK_SECRET: str = "changeme-webhook-secret"

    # LLM providers
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY:    str = ""
    QWEN_API_KEY:      str = ""
    DEEPSEEK_API_KEY:  str = ""

    # Storage (MinIO / S3-compatible)
    AWS_ACCESS_KEY_ID:     str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_ENDPOINT_URL:      str = "http://localhost:9000"
    S3_BUCKET_NAME:        str = "hexa-hub-assets"

    # Platform publishing
    LINKEDIN_ACCESS_TOKEN:      str = ""
    LINKEDIN_PERSON_URN:        str = ""
    META_ACCESS_TOKEN:          str = ""
    META_IG_USER_ID:            str = ""
    FACEBOOK_PAGE_ID:           str = ""
    FACEBOOK_PAGE_ACCESS_TOKEN: str = ""
    WORDPRESS_URL:              str = ""
    WORDPRESS_APP_PASSWORD:     str = ""

    # Webhook for XHS / WeChat manual publishing packages
    WEBHOOK_URL: str = ""

    # Public URL (used to build image URLs for uploaded files)
    PUBLIC_BACKEND_URL: str = "http://localhost:8000"

    # Frontend URL (used for OAuth redirect URIs)
    FRONTEND_URL: str = "https://hexahub-console.vercel.app"

    # Meta (Facebook / Instagram) OAuth app credentials
    META_APP_ID:     str = ""
    META_APP_SECRET: str = ""

    # LinkedIn OAuth app credentials
    LINKEDIN_CLIENT_ID:     str = ""
    LINKEDIN_CLIENT_SECRET: str = ""

    # Google Drive asset browser
    GOOGLE_DRIVE_API_KEY:   str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""

    # App
    DEBUG:        bool = False
    DOCS_ENABLED: bool = True

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
