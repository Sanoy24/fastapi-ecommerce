from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


engine = create_engine(settings.Database_url, connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def check_db_health(db: Session) -> bool:
    """
    Attempts to execute a minimal query to verify database connection.
    """
    try:
        db.execute(text("SELECT 1 "))
        return True
    except Exception:
        return False
