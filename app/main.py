from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.routes import healthcheck, user
from sqlalchemy.exc import SQLAlchemyError
from app.middleware.request_logger import LoggingMiddleware
from app.core.logger import logger


app = FastAPI(root_path="/api/v1")
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
    # Detect Pydantic’s raw TypeError before it crashes
    if isinstance(exc, TypeError) and "max_digits" in str(exc):
        logger.warning(f"Pydantic TypeError caught: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.info(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


app.include_router(router=healthcheck.router, prefix="/healthcheck")
app.include_router(router=user.router, prefix="/users")
