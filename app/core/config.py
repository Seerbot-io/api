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
    # Used to sign on-chain withdraw transactions.
    # Accepts either a filesystem path to a *.skey file or a CBOR hex string.
    VAULT_WITHDRAW_SIGNING_KEY: str | None = None
    # Bech32 address corresponding to the withdraw signing key (fee payer / change address).
    # Cardano network selector for Blockfrost base URL.
    CARDANO_NETWORK: str = "mainnet"

    # Token price cache settings
    TOKEN_CACHE_ENABLE_BACKGROUND_REFRESH: bool = False
    TOKEN_CACHE_REFRESH_INTERVAL: int = 15  # seconds
    TOKEN_CACHE_INFO_TTL: int = 3600  # 1 hour in seconds
    TOKEN_CACHE_PRICE_TTL: int = 30  # 30 seconds


# Instantiate the settings
settings = Settings()  # type: ignore
