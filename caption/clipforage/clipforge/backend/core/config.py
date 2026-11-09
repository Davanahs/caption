from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "ClipForge"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    SCORING_MODE: str = "prod"  # "prod" or "test"
    PUBLISH_MODE: str = "prod"  # "prod" or "test"

    # Security
    SECRET_KEY: str = "clipforge_default_secret_key_change_in_prod"
    STORAGE_IDENTITY_SECRET: str = ""

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clipforge_user:clipforge_password@localhost:5433/clipforge"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://clipforge_user:clipforge_password@localhost:5433/clipforge"

    # Connection Pooling
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 1800  # 30 minutes
    CELERY_TASK_TIME_LIMIT: int = 1860       # 31 minutes

    # YouTube OAuth
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""
    YOUTUBE_TOKEN_FILE: str = "/app/tokens/youtube_token.json"
    YOUTUBE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/publish/oauth-callback"

    # Cloud APIs (OpenRouter, Groq, Nvidia)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "whisper-large-v3-turbo"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "deepseek/deepseek-r1:free"
    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.1-405b-instruct"
    PEXELS_API_KEY: str = ""

    # Whisper
    WHISPER_MODEL: str = "base"  # tiny/base/small/medium/large

    # Clip Settings
    MIN_CLIP_DURATION: int = 15
    MAX_CLIP_DURATION: int = 40
    CLIPS_PER_VIDEO: int = 5
    REFRAME_MODE: str = "blur"  # crop | fit | blur | template

    # ── Phase 6: Storage Lifecycle & MinIO/S3 ──────────────────────────────
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "clipforge"
    S3_REGION: str = "us-east-1"
    
    RETENTION_TEMP_HOURS: int = 24
    RETENTION_PERSISTENT_DAYS: int = 30
    STORAGE_CLEANUP_INTERVAL_SECONDS: int = 3600


    # Notifications (Phase 4)
    NOTIFICATION_WEBHOOK_URL: str = ""   # Discord / Slack / n8n webhook URL
    NOTIFICATION_EMAIL: str = ""         # Recipient email for clip alerts
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""

    # Channel Automation
    CHANNEL_CHECK_INTERVAL_MINUTES: int = 30

    # ── Content ID Bypass ──────────────────────────────────────────────────
    # Applies subtle FFmpeg transforms so clips avoid YouTube's copyright fingerprint scanner
    CONTENT_ID_BYPASS: bool = False
    BYPASS_SPEED: float = 1.02       # Speed up by 5% — disrupts audio/video timing fingerprint
    BYPASS_MIRROR: bool = False      # Flip video horizontally — set true for extra protection
    BYPASS_COLOR_GRADE: bool = False # Tiny brightness/contrast/saturation shift — barely visible

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://*.netlify.app"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
