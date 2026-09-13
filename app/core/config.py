from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Setting(BaseSettings):
    Database_url: str = "postgresql://postgres:postgres@localhost:5432/ecommerce"
    JWT_ALGORITHM: str = "HS256"
    # No default: an empty/unset signing key would let anyone forge tokens by
    # HMAC-signing with "". min_length guards against trivially weak secrets too.
    JWT_SECRET_KEY: str = Field(..., min_length=32)
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

    # OAuth (social login) — registered with each provider's own developer
    # console. OAUTH_REDIRECT_URI is a single shared callback page on the
    # frontend (it reads `code`/`state` off its own URL and POSTs them to
    # this API); it must match exactly what's registered with each provider.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:3000/auth/callback"

    # Every product price is stored in this currency — see
    # app/models/currency.py for how other currencies convert from it.
    BASE_CURRENCY_CODE: str = "USD"

    # How many loyalty points a customer earns per 1 unit of order total in
    # BASE_CURRENCY_CODE — see PaymentService._handle_successful_payment.
    POINTS_EARNED_PER_BASE_CURRENCY_UNIT: float = 1.0
    # How much discount (in BASE_CURRENCY_CODE) redeeming 1 point is worth
    # at checkout — see calculate_points_discount in app/services/pricing.py.
    POINTS_REDEMPTION_VALUE: float = 0.01

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

