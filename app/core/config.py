from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Setting(BaseSettings):
    Database_url: str = "postgresql://postgres:postgres@localhost:5432/ecommerce"
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = ""
    JWT_DEFAULT_EXP_MINUTES: int = 30
    JWT_REFRESH_EXP_DAYS: int = 7
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    ELASTIC_URL: str = "http://elasticsearch:9200"

    # CORS — comma-separated origins in .env, e.g. "http://localhost:3000,https://myapp.com"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_NAME: str = "E-Commerce Store"
    EMAILS_FROM_ADDRESS: str = ""

    # Frontend base URL (used in password-reset links)
    FRONTEND_URL: str = "http://localhost:3000"

    # File storage: "local" or "s3"
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "uploads"
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    AWS_ACCESS_KEY: str = ""
    AWS_SECRET_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Setting()

