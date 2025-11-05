from app.schema.user_schema import (
    CreateUserSchema,
    UserPublic,
    LoginSchema,
    TokenSchema,
)
from app.models.user import User
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.crud.user import UserCrud
from app.utils.security import verify_password, create_token


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = UserCrud(db=db)

    def create_user(self, user_create_data: CreateUserSchema) -> UserPublic:
        if self.crud.get_user_by_email(user_create_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        user = self.crud.create_user(user_create_data=user_create_data)
        return UserPublic.model_validate(user)

    def authenticate_user(self, user_login_data: LoginSchema) -> User:
        user = self.crud.get_user_by_email(email=user_login_data.email)
        if not user:
            return None
        if not verify_password(user_login_data.password, user.password_hash):
            return None
        return user

    def login(self, user_login_data: LoginSchema) -> TokenSchema:
        user = self.authenticate_user(user_login_data=user_login_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        access_token_payload = {"id": user.id}
        access_token = create_token(data=access_token_payload)
        return TokenSchema(token=access_token, token_type="Bearer")
