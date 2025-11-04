from fastapi import APIRouter, Depends
from app.schema.user_schema import CreateUserSchema
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_user_service_dep
from app.services.user_service import UserService

router = APIRouter(tags=["User"])


@router.post("/register")
async def create_user(
    create_user_data: CreateUserSchema,
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service_dep),
):
    user = user_service.create_user(create_user_data)
    return user
