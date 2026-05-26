from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from config import settings

DB_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), settings.DB_DIR))
os.makedirs(DB_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, settings.DB_NAME)}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.ECHO_SQL,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
