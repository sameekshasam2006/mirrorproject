from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MIRROR"
    secret_key: str = "change-me-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./mirror.db"
    frontend_origin: str = "http://localhost:5173"
    app_env: str = "development"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()

if settings.app_env.lower() == "production" and (
    settings.secret_key == "change-me-secret-key" or len(settings.secret_key) < 32
):
    raise RuntimeError("Production requires a SECRET_KEY of at least 32 characters.")
