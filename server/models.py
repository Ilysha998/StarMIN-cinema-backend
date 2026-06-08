from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class Hall(Base):
    __tablename__ = "halls"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    layout = Column(JSON, nullable=False)
    break_minutes = Column(Integer, nullable=False, default=15)
    base_price = Column(Float, nullable=False, default=250.0)

    sessions = relationship("Session", back_populates="hall")

    def seat_count(self) -> int:
        if isinstance(self.layout, list):
            return sum(1 for row in self.layout for seat in row if seat != "empty")
        return 0

    def __repr__(self):
        return f"<Hall(id={self.id}, name={self.name})>"


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    genre = Column(String(100), nullable=False)
    duration = Column(Integer, nullable=False)
    age_restriction = Column(Integer, nullable=False, default=0)
    poster_url = Column(String(500), nullable=True)

    sessions = relationship("Session", back_populates="movie", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Movie(id={self.id}, title={self.title}, genre={self.genre}, age={self.age_restriction}+)>"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    hall_id = Column(Integer, ForeignKey("halls.id"), nullable=False, index=True)
    datetime = Column(DateTime, nullable=False, index=True)
    price = Column(Float, nullable=False)

    movie = relationship("Movie", back_populates="sessions")
    hall = relationship("Hall", back_populates="sessions")
    tickets = relationship("Ticket", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session(id={self.id}, movie_id={self.movie_id}, hall_id={self.hall_id}, datetime={self.datetime})>"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("session_id", "seat_row", "seat_col", name="uq_ticket_seat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    seat_row = Column(Integer, nullable=False)
    seat_col = Column(Integer, nullable=False)
    seat_type = Column(String(20), nullable=False, default="standard")
    price = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    qr_token = Column(String(64), unique=True, nullable=False, index=True)

    session = relationship("Session", back_populates="tickets")
    user = relationship("User", back_populates="tickets")

    def __repr__(self):
        return f"<Ticket(id={self.id}, session_id={self.session_id}, row={self.seat_row}, col={self.seat_col})>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)

    tickets = relationship("Ticket", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, login={self.login}, is_admin={self.is_admin})>"
