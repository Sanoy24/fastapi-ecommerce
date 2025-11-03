from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from app.core.config import setting
from typing import Generator

engine = create_engine(setting.Database_url, connect_args={"check_same_thread": False})
Base = declarative_base()

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health(db: Session) -> bool:
    """
    Attempts to execute a minimal query to verify database connection.
    """
    try:
        db.execute(text("SELECT 1 "))
        return True
    except Exception:
        return False
