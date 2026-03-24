from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://fointel:fointel@127.0.0.1:5434/fo_intel"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


app_settings = Settings()
