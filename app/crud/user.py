from datetime import datetime, timedelta
from sqlalchemy import func, or_
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
                password_hash=hashed_password,
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

    def get_total_users(self):
        total_users = self.db.query(func.count(User.id)).scalar() or 0
        return total_users

    def get_total_customers(self):
        total_customers = (
            self.db.query(func.count(User.id)).filter(User.role == "customer").scalar()
            or 0
        )
        return total_customers

    def get_total_admins(self):
        total_admins = (
            self.db.query(func.count(User.id)).filter(User.role == "admin").scalar()
            or 0
        )
        return total_admins

    def get_new_user_in_last_thirty_days(self):
        thirty_days_ago = datetime.now() - timedelta(days=30)
        new_user_last_30_days = (
            self.db.query(func.count(User.id))
            .filter(User.created_at >= thirty_days_ago)
            .scalar()
            or 0
        )
        return new_user_last_30_days

    def get_all_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
    ):
        query = self.db.query(User)
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
            query = query.filter(search_filter)
        if role:
            query = query.filter(User.role == role)
        total = query.count()
        offset = (page - 1) * page_size
        users = query.offset(offset).limit(page_size).all()
        return total, users

    def update_user_role(self, user_id: int, new_role: str) -> User:
        """Update a user's role"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.role = new_role
        self.db.commit()
        self.db.refresh(user)
        return user
