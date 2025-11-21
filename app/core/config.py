import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(override=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "SeerBot"
    # Application settings
    PORT: int | None 
    HOST: str | None
    STATIC_FOLDER: str | None
    VERSION: str | None
    DOC_PASSWORD: str | None
    SESSION_SECRET_KEY: str | None

    # SSL settings
    SSL_KEY: str | None
    SSL_CERT: str | None

    # SQLAlchemy database URL
    DATABASE_URL: str
    # MySQL settings

    SCHEMA_1: str | None
    SCHEMA_2: str | None
    SCHEMA_3: str | None
    SCHEMA_4: str | None
    SCHEMA_5: str | None


    # Login configuration
    ENCODE_KEY: str | None
    ENCODE_ALGORITHM: str | None = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int | None = 1800 # 30 minutes
    NONCE_EXPIRY_SECONDS: int | None = 300 # 5 minutes

    # Redis settings
    REDIS_HOST: str | None
    REDIS_PORT: int | None
    REDIS_MAX_CONNECTIONS: int | None
    REDIS_SSL: bool | None
    
    # Debug settings
    DEBUG: bool = False

    # Chat GPT settings
    GPT_KEY: str | None
     
    class Config:
        env_file = ".env"

# Instantiate the settings
settings = Settings()