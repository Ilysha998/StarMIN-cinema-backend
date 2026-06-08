from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "StarMIN Cinema Backend"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "API для системы кинотеатра"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    RELOAD: bool = True

    DB_DIR: str = "../database"
    DB_NAME: str = "cinema.db"
    ECHO_SQL: bool = False
    MOVIE_POOL: list[dict] = []

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100

    MAX_SEATS_PER_PURCHASE: int = 6
    MAX_SEATS_PER_USER_PER_SESSION: int = 8

    SEAT_TYPE_MULTIPLIERS: dict[str, float] = {
        "standard": 1.0,
        "sofa": 1.5,
    }

    FIRST_SESSION_HOUR: int = 10
    LAST_SESSION_HOUR: int = 23

    PRICE_MORNING_MULTIPLIER: float = 0.8
    PRICE_MORNING_BEFORE_HOUR: int = 14
    PRICE_EVENING_MULTIPLIER: float = 1.2
    PRICE_EVENING_AFTER_HOUR: int = 21

    CLEANUP_HOURS_AGO: int = 2

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 3
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

DEFAULT_HALL_LAYOUTS = {
    "1": {
        "layout": [["standard"] * 10 for _ in range(10)],
        "base_price": settings.HALL_1_BASE_PRICE if hasattr(settings, "HALL_1_BASE_PRICE") else 250.0,
        "break_minutes": 15,
    },
    "2": {
        "layout": [
            ["standard"] * 12,
            ["standard"] * 12,
            ["standard"] * 12,
            ["standard"] * 12,
            ["standard"] * 10 + ["empty"] * 2,
            ["standard"] * 10 + ["empty"] * 2,
            ["standard"] * 8 + ["empty"] * 4,
            ["standard"] * 8 + ["empty"] * 4,
        ],
        "base_price": 300.0,
        "break_minutes": 15,
    },
    "vip": {
        "layout": [
            ["sofa", "sofa", "empty", "sofa", "sofa", "empty", "sofa", "sofa"],
            ["sofa", "sofa", "empty", "sofa", "sofa", "empty", "sofa", "sofa"],
            ["standard", "standard", "empty", "standard", "standard", "empty", "standard", "standard"],
            ["standard", "standard", "standard", "standard", "standard", "standard", "empty", "empty"],
            ["standard", "standard", "standard", "standard", "standard", "standard", "empty", "empty"],
        ],
        "base_price": 500.0,
        "break_minutes": 20,
    },
}
