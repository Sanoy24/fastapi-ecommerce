from app.schema.user_schema import CreateUserSchema, UserResponse
from app.models.user import User
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.crud.user import UserCrud


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = UserCrud(db=db)

    def create_user(self, user_create_data: CreateUserSchema) -> UserResponse:
        if self.crud.get_user_by_email(user_create_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        user = self.crud.create_user(user_create_data=user_create_data)
        return UserResponse.model_validate(user)

    def get_user():
        pass
