from app.db.database import SessionLocal
from typing import Generator
from sqlalchemy.orm import Session
from fastapi import Depends
from app.services.user_service import UserService


def get_db() -> Generator:
    """
    Local db Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_service_dep(db: Session = Depends(get_db)) -> UserService:
    """
    User service dependency
    """
    return UserService(db=db)
