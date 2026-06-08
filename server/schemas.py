from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime as dt_datetime
from typing import Optional, List
from enum import Enum


class SeatType(str, Enum):
    standard = "standard"
    sofa = "sofa"
    empty = "empty"


class SeatPosition(BaseModel):
    row: int = Field(..., ge=0, description="Ряд (0-индексированный)")
    col: int = Field(..., ge=0, description="Место в ряду (0-индексированный)")


# Схемы залов

class HallBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Название зала")
    layout: List[List[SeatType]] = Field(..., description="2D схема мест (standard/sofa/empty)")
    break_minutes: int = Field(15, gt=0, description="Перерыв между сеансами (мин)")
    base_price: float = Field(250.0, gt=0, description="Базовая цена билета")


class HallCreate(HallBase):
    pass


class HallUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    layout: Optional[List[List[SeatType]]] = None
    break_minutes: Optional[int] = Field(None, gt=0)
    base_price: Optional[float] = Field(None, gt=0)


class HallResponse(BaseModel):
    id: int
    name: str
    layout: List[List[str]]
    break_minutes: int
    base_price: float
    seat_count: int

    model_config = ConfigDict(from_attributes=True)


# Схемы кинца

class MovieBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Название фильма")
    genre: str = Field(..., min_length=1, max_length=100, description="Жанр фильма")
    duration: int = Field(..., gt=0, description="Длительность в минутах")
    age_restriction: int = Field(..., ge=0, le=18, description="Возрастное ограничение (0, 6, 12, 16, 18)")
    poster_url: Optional[str] = Field(None, max_length=500, description="URL постера")


class MovieCreate(MovieBase):
    pass


class MovieUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    genre: Optional[str] = Field(None, min_length=1, max_length=100)
    duration: Optional[int] = Field(None, gt=0)
    age_restriction: Optional[int] = Field(None, ge=0, le=18)
    poster_url: Optional[str] = Field(None, max_length=500)


class MovieResponse(MovieBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Схемы сеансов

class SessionBase(BaseModel):
    movie_id: int = Field(..., gt=0, description="ID фильма")
    hall_id: int = Field(..., gt=0, description="ID зала")
    datetime: dt_datetime = Field(..., description="Дата и время сеанса")
    price: float = Field(..., gt=0, description="Базовая цена билета")


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    movie_id: Optional[int] = Field(None, gt=0)
    hall_id: Optional[int] = Field(None, gt=0)
    datetime: Optional[dt_datetime] = None
    price: Optional[float] = Field(None, gt=0)


class SessionResponse(SessionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Схемы билетов

class TicketBase(BaseModel):
    session_id: int = Field(..., gt=0, description="ID сеанса")
    seat_row: int = Field(..., ge=0, description="Ряд")
    seat_col: int = Field(..., ge=0, description="Место в ряду")
    seat_type: str = Field("standard", description="Тип места")
    price: float = Field(..., gt=0, description="Цена билета")
    is_paid: bool = Field(False, description="Оплачен ли билет")
    user_id: Optional[int] = Field(None, description="ID пользователя")


class MultiTicketCreate(BaseModel):
    session_id: int = Field(..., gt=0, description="ID сеанса")
    seats: List[SeatPosition] = Field(..., min_length=1, description="Список мест для покупки")
    phone: Optional[str] = Field(None, max_length=20, description="Телефон для связи")
    email: Optional[str] = Field(None, max_length=255, description="Email для связи")

    @model_validator(mode="after")
    def _no_duplicate_seats(self):
        seen = set()
        for s in self.seats:
            key = (s.row, s.col)
            if key in seen:
                raise ValueError(f"Дублирующееся место: ряд {s.row}, место {s.col}")
            seen.add(key)
        return self


class TicketCreate(BaseModel):
    session_id: int = Field(..., gt=0)
    seat_row: int = Field(..., ge=0)
    seat_col: int = Field(..., ge=0)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)


class TicketUpdate(BaseModel):
    is_paid: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    qr_token: Optional[str] = Field(None, description="QR-токен для анонимной оплаты")


class TicketResponse(BaseModel):
    id: int
    session_id: int
    user_id: Optional[int] = None
    seat_row: int
    seat_col: int
    seat_type: str
    price: float
    is_paid: bool
    qr_token: str
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketBrief(BaseModel):
    id: int
    session_id: int
    seat_row: int
    seat_col: int
    seat_type: str
    price: float
    is_paid: bool
    qr_token: str

    model_config = ConfigDict(from_attributes=True)


class SessionWithTickets(SessionResponse):
    tickets: List[TicketBrief] = []

    model_config = ConfigDict(from_attributes=True)


# Схема карты мест

class SeatMapCell(BaseModel):
    type: str
    status: str


class SeatMapResponse(BaseModel):
    session_id: int
    hall_id: int
    hall_name: str
    seat_map: List[List[SeatMapCell]]
    available_count: int
    booked_count: int
    total_seats: int


# Схемы юзеров

class UserBase(BaseModel):
    login: str = Field(..., min_length=3, max_length=100, description="Логин пользователя")
    is_admin: bool = Field(False, description="Администратор ли")
    phone: Optional[str] = Field(None, max_length=20, description="Телефон")
    email: Optional[str] = Field(None, max_length=255, description="Email")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=255, description="Пароль")


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=255)
    is_admin: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)


class UserResponse(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    login: str
    is_admin: bool
