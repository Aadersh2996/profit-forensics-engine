"""Application configuration loaded from environment variables and ``.env``."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings shared by the API, database, and graph runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Profit Forensics Engine", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")
    database_url: str = Field(
        default="sqlite:///./profit_forensics.db", validation_alias="DATABASE_URL"
    )
    upload_dir: Path = Field(default=Path("./uploads"), validation_alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=20, validation_alias="MAX_UPLOAD_SIZE_MB")
    confidence_threshold: float = Field(
        default=0.7, validation_alias="CONFIDENCE_THRESHOLD"
    )
    razorpay_key_id: str | None = Field(default=None, validation_alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: str | None = Field(default=None, validation_alias="RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str | None = Field(
        default=None, validation_alias="RAZORPAY_WEBHOOK_SECRET"
    )
    razorpay_api_base_url: str = Field(
        default="https://api.razorpay.com/v1", validation_alias="RAZORPAY_API_BASE_URL"
    )
    razorpay_timeout_seconds: float = Field(
        default=15.0, validation_alias="RAZORPAY_TIMEOUT_SECONDS"
    )

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_max_upload_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be greater than zero")
        return value

    @field_validator("confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return value

    @field_validator("razorpay_timeout_seconds")
    @classmethod
    def validate_razorpay_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("RAZORPAY_TIMEOUT_SECONDS must be greater than zero")
        return value


settings = Settings()
