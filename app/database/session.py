import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from collections.abc import Generator

from sqlalchemy.orm import Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from the .env file.")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,   # check the connection is alive before using it
    pool_recycle=280,     # proactively recycle before Neon's idle timeout
    connect_args={"connect_timeout": 10},  # fail fast instead of hanging forever
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()