from app.models.user import User
from sqlalchemy.orm import Session
from pydantic import EmailStr
from typing import Optional
from app.schema.user_schema import CreateUserSchema, UpdateUserSchema
from app.utils.security import hash_password
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status


class UserCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user_create_data: CreateUserSchema) -> User:
        """
        Create a new user
        """
        try:
            hashed_password = hash_password(user_create_data.password)
            db_user = User(
                **user_create_data.model_dump(exclude={"password"}),
                password_hash=hashed_password
            )
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            return db_user
        except SQLAlchemyError as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    def get_user(self, user_id: int) -> Optional[User]:
        """
        Retrieve a single user by ID.
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: EmailStr) -> Optional[User]:
        """
        Retrieve a single user by email
        """
        return self.db.query(User).filter(User.email == email).first()
