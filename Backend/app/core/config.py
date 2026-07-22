from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    OTP_EXPIRE_MINUTES: int
    INVITATION_EXPIRE_DAYS: int

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_EMAIL: str
    SMTP_PASSWORD: str

    FRONTEND_URL: str
    API_KEY_ENCRYPTION_KEY: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
