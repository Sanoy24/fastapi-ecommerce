from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.v1.routes import healthcheck, user
from sqlalchemy.exc import SQLAlchemyError
from app.middleware.request_logger import LoggingMiddleware


app = FastAPI(root_path="/api/v1")
app.add_middleware(LoggingMiddleware)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Please try again later."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


app.include_router(router=healthcheck.router, prefix="/healthcheck")
app.include_router(router=user.router, prefix="/users")
