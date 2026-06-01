import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "In-Game Purchases API")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = os.getenv("JWT_ISSUER", "in-game-purchases-api")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "in-game-purchases-client")
    token_clock_skew_seconds: int = int(os.getenv("TOKEN_CLOCK_SKEW_SECONDS", "30"))
    max_token_bytes: int = int(os.getenv("MAX_TOKEN_BYTES", "4096"))
    access_token_ttl_minutes: int = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "15"))
    refresh_token_ttl_days: int = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))
    password_hash_iterations: int = int(os.getenv("PASSWORD_HASH_ITERATIONS", "390000"))
    refund_window_minutes: int = int(os.getenv("REFUND_WINDOW_MINUTES", "120"))
    allow_admin_refund_after_window: bool = (
        os.getenv("ALLOW_ADMIN_REFUND_AFTER_WINDOW", "true").lower() == "true"
    )
    require_inventory_for_refund: bool = (
        os.getenv("REQUIRE_INVENTORY_FOR_REFUND", "true").lower() == "true"
    )

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://app:app@postgres:5432/game_store",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_key_prefix: str = os.getenv("REDIS_KEY_PREFIX", "igs:mvp")
    purchase_reserve_ttl_seconds: int = int(
        os.getenv("PURCHASE_RESERVE_TTL_SECONDS", "30")
    )
    sql_echo: bool = os.getenv("SQL_ECHO", "false").lower() == "true"


settings = Settings()
