from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime as dt_datetime
from typing import Optional, List
from enum import Enum


class HallEnum(str, Enum):
    hall_1 = "1"
    hall_2 = "2"
    hall_vip = "vip"


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


# Схемы сеансов показа кина

class SessionBase(BaseModel):
    movie_id: int = Field(..., gt=0, description="ID фильма")
    datetime: dt_datetime = Field(..., description="Дата и время сеанса")
    hall: HallEnum = Field(..., description="Зал: 1, 2, vip")
    price: float = Field(..., gt=0, description="Цена билета")


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    movie_id: Optional[int] = Field(None, gt=0)
    datetime: Optional[dt_datetime] = None
    hall: Optional[HallEnum] = None
    price: Optional[float] = Field(None, gt=0)


class SessionResponse(SessionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Схемы билетов

class TicketBase(BaseModel):
    session_id: int = Field(..., gt=0, description="ID сеанса")
    seat_number: int = Field(..., gt=0, description="Номер места")
    is_paid: bool = Field(False, description="Оплачен ли билет")
    user_id: Optional[int] = Field(None, description="ID пользователя (если авторизован)")


class TicketCreate(BaseModel):
    session_id: int = Field(..., gt=0)
    seat_number: int = Field(..., gt=0)
    phone: Optional[str] = Field(None, max_length=20, description="Телефон для связи")
    email: Optional[str] = Field(None, max_length=255, description="Email для связи")


class TicketUpdate(BaseModel):
    is_paid: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)


class TicketResponse(TicketBase):
    id: int
    qr_token: str
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketBrief(BaseModel):
    id: int
    session_id: int
    seat_number: int
    is_paid: bool
    qr_token: str

    model_config = ConfigDict(from_attributes=True)


class SessionWithTickets(SessionResponse):
    tickets: List[TicketBrief] = []

    model_config = ConfigDict(from_attributes=True)


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
