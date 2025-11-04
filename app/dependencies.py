from app.db.database import SessionLocal
from typing import Generator
from sqlalchemy.orm import Session
from fastapi import Depends
from app.services.user_service import UserService


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_service_dep(db: Session = Depends(get_db)):
    return UserService(db=db)
