from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

engine = create_engine(
    settings.Database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


# NOTE: Schema management is handled exclusively by Alembic migrations.
# Do NOT call Base.metadata.create_all() here in production code.

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

