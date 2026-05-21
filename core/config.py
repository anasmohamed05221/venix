from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    ENV: str = "development"
    
    DATABASE_URL: str
    TEST_DATABASE_URL: Optional[str] = None
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    RESEND_API_KEY: str = ""
    MAIL_FROM: str
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    REDIS_URL: str = "redis://localhost:6379/0"
    BASE_URL: str = "http://localhost:8000"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_SUCCESS_URL: str = "http://localhost:3000/checkout/success"
    FRONTEND_CANCEL_URL: str = "http://localhost:3000/checkout/cancel"


settings = Settings()