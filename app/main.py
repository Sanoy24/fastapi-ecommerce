from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.init_routes import init_routes
from app.api.v1.routes import healthcheck, user, category, product, cart
from sqlalchemy.exc import SQLAlchemyError
from app.middleware.request_logger import LoggingMiddleware
from app.core.logger import logger
from pydantic import BaseModel

from app.utils.seed import seed_product


class RootResponse(BaseModel):
    message: str


app = FastAPI(
    # --- Metadata for Documentation (Title and Description are crucial) ---
    title="E-Commerce Backend API",
    description="RESTful API for managing the product catalog, user authentication, shopping carts, and order processing for the online store.",
    version="1.0.0",
    # --- Additional OpenAPI Metadata ---
    contact={
        "name": "Yonas Mekonnen",
        "email": "myonas886@gmail.com",
        "url": "https://yonas-mekonnen-portfolio.vercel.app/",
    },
    license_info={
        "name": "MIT",  # Or your preferred license (e.g., Apache 2.0)
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "products",
            "description": "Operations related to product catalog management.",
        },
        {
            "name": "users",
            "description": "User authentication and profile management.",
        },
        {
            "name": "carts",
            "description": "Shopping cart operations.",
        },
        {
            "name": "orders",
            "description": "Order processing and history.",
        },
    ],
    # --- Servers for Multi-Environment Support ---
    # --- Path Configuration ---
    # Sets the base path for all routes, essential if your API runs behind a proxy or gateway.
    root_path="/api/v1",
    servers=[],
    # Sets the documentation path. Since root_path is set to /api/v1,
    # setting docs_url to "/docs" will result in the final path /api/v1/docs.
    docs_url="/docs",
    redoc_url="/redoc",
    # --- Optional: Custom OpenAPI Schema Overrides ---
    # You can override the OpenAPI schema function if needed for custom logic
    # openapi_url="/openapi.json",
)

app.add_middleware(LoggingMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for e in exc.errors():
        field = ".".join(map(str, e["loc"][1:]))  # skip 'body'
        errors[field] = e["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Validation failed for one or more fields.",
            "fields": errors,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Please try again later."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.info(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


@app.get("/", tags=["Root"], response_model=RootResponse)
def read_root():
    """Returns a welcome message for the API root."""
    return {
        "message": "Welcome to the E-Commerce API v1. Check out /docs for the spec!"
    }


init_routes(app)

# seed_product()
