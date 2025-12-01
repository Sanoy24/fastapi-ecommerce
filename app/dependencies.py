from typing import Annotated, Generator, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.elastic_config import get_es_client
from app.core.logger import *
from app.core.redis import RedisClient, redis_client
from app.db.database import SessionLocal
from app.models.user import User
from app.schema.user_schema import UserPublic
from app.services.address_service import AddressService
from app.services.cart_service import CartService
from app.services.category_service import CategoryService
from app.services.elasticsearch_service import ElasticService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.product_service import ProductService
from app.services.review_service import ReviewService
from app.services.user_service import UserService
from app.utils.security import TokenError, decode_access_token

oauth_scheme = HTTPBearer(
    scheme_name="Bearer",
    auto_error=False,
    description="JWT Access Token in the Authorization header",
)


def get_db() -> Generator[Session, None, None]:
    """
    Local db Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_redis_manager() -> RedisClient:
    return redis_client


async def get_elastic_manager() -> AsyncElasticsearch:
    return await get_es_client()


def get_user_service_dep(db: Session = Depends(get_db)) -> UserService:
    """
    User service dependency
    """
    return UserService(db=db)


def get_elastic_service_dep(
    es: Annotated[AsyncElasticsearch, Depends(get_elastic_manager)],
) -> ElasticService:
    return ElasticService(es=es)


def get_address_service_dep(db: Session = Depends(get_db)) -> AddressService:
    """
    Address service dependency
    """
    return AddressService(db=db)


def get_category_service_dep(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db=db)


def get_product_service_dep(
    db: Annotated[Session, Depends(get_db)],
    redis_client: Annotated[RedisClient, Depends(get_redis_manager)],
) -> ProductService:
    return ProductService(db=db, redis=redis_client)


def get_cart_service_dep(db: Annotated[Session, Depends(get_db)]) -> CartService:
    return CartService(db=db)


def get_order_service_dep(db: Annotated[Session, Depends(get_db)]) -> OrderService:
    return OrderService(db=db)


def get_review_service_dep(db: Annotated[Session, Depends(get_db)]) -> ReviewService:
    return ReviewService(db=db)


def get_payment_service_dep(db: Annotated[Session, Depends(get_db)]) -> PaymentService:
    return PaymentService(db=db)


async def get_current_user(
    user_service: Annotated[UserService, Depends(get_user_service_dep)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(oauth_scheme)],
) -> UserPublic:
    """
    Get current authenticated user from JWT token
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded_token = decode_access_token(token=credentials.credentials)
        logger.info(f"decoded token: {decoded_token}")

        user_id = decoded_token.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = user_service.get_user_by_id(id=int(user_id))
        return UserPublic.model_validate(user)

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(
    current_user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


async def get_optional_user(
    user_service: Annotated[UserService, Depends(get_user_service_dep)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(oauth_scheme)],
) -> UserPublic:
    if not credentials:
        return None

    try:
        decoded = decode_access_token(credentials.credentials)
        user_id = decoded.get("sub")

        if not user_id:
            return None

        user = user_service.get_user_by_id(id=int(user_id))
        return UserPublic.model_validate(user)

    except Exception:
        return None
        return None
