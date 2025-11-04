from app.models.user import User
from sqlalchemy.orm import Session
from pydantic import EmailStr
from typing import Optional
from app.schema.user_schema import CreateUserSchema
from app.utils.security import hash_password


class UserCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user_create_data: CreateUserSchema) -> User:
        """
        Create a new user
        """
        hashed_password = hash_password(user_create_data.password)
        db_user = User(
            **user_create_data.model_dump(exclude={"password"}),
            password_hash=hashed_password
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

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
