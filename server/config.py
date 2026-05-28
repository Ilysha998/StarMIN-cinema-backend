from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "StarMIN Cinema Backend"
    APP_VERSION: str = "1.2.0"
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

    HALL_1_SEATS: int = 100
    HALL_1_BASE_PRICE: float = 250
    HALL_1_BREAK_MINUTES: int = 15

    HALL_2_SEATS: int = 80
    HALL_2_BASE_PRICE: float = 300
    HALL_2_BREAK_MINUTES: int = 15

    HALL_VIP_SEATS: int = 30
    HALL_VIP_BASE_PRICE: float = 500
    HALL_VIP_BREAK_MINUTES: int = 20

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


HALL_CONFIG = {
    "1": {
        "seats": settings.HALL_1_SEATS,
        "base_price": settings.HALL_1_BASE_PRICE,
        "break_minutes": settings.HALL_1_BREAK_MINUTES,
    },
    "2": {
        "seats": settings.HALL_2_SEATS,
        "base_price": settings.HALL_2_BASE_PRICE,
        "break_minutes": settings.HALL_2_BREAK_MINUTES,
    },
    "vip": {
        "seats": settings.HALL_VIP_SEATS,
        "base_price": settings.HALL_VIP_BASE_PRICE,
        "break_minutes": settings.HALL_VIP_BREAK_MINUTES,
    },
}

HALLS = list(HALL_CONFIG.keys())
