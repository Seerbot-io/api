from pycardano import Network
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    PROJECT_NAME: str = "SeerBot"
    # Application settings
    PORT: int
    HOST: str
    STATIC_FOLDER: str
    VERSION: str
    DOC_PASSWORD: str
    SESSION_SECRET_KEY: str

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
    ACCESS_TOKEN_EXPIRE_SECONDS: int | None = 1800  # 30 minutes
    NONCE_EXPIRY_SECONDS: int | None = 300  # 5 minutes

    # Redis settings
    REDIS_HOST: str | None
    REDIS_PORT: int | None
    REDIS_MAX_CONNECTIONS: int | None
    REDIS_SSL: bool | None
    # Memory cache settings
    MEMORY_CACHE_MAX_SIZE: int = 4 * 1024 * 1024 * 1024  # 4GB in bytes
    REDIS_RECHECK_INTERVAL: int = 30 * 60  # 30 minutes in seconds

    # Debug settings
    DEBUG: bool = False

    # Chat GPT settings
    GPT_KEY: str | None

    # CARDANO
    BLOCKFROST_API_KEY: str
    CARDANO_NETWORK: Network = Network.MAINNET

    # Token price cache settings
    TOKEN_CACHE_ENABLE_BACKGROUND_REFRESH: bool = False
    TOKEN_CACHE_REFRESH_INTERVAL: int = 15  # seconds
    TOKEN_CACHE_INFO_TTL: int = 3600  # 1 hour in seconds
    TOKEN_CACHE_PRICE_TTL: int = 30  # 30 seconds

    @field_validator("CARDANO_NETWORK", mode="before")
    @classmethod
    def map_mode(cls, v):
        if isinstance(v, Network):
            return v

        if isinstance(v, str):
            v = v.lower()
            if v == "mainnet":
                return Network.MAINNET
            if v in ("preprod", "testnet"):
                return Network.TESTNET

        raise ValueError(f"Invalid network: {v}")
# Instantiate the settings
settings = Settings()  # type: ignore
