from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.init_routes import init_routes
from app.core.config import settings
from app.core.elastic_config import close_es_client, get_es_client
from app.core.logger import logger

from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.middleware.request_logger import LoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.utils.idempotency import IdempotentResponseException
from fastapi.responses import JSONResponse

from app.core.redis import redis_client
from app.middleware.request_logger import LoggingMiddleware
from app.utils.es_utils import bulk_index_products, create_product_index
from app.workers.reservation_cleanup import cleanup_expired_reservations_loop
import asyncio
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend


from arq import create_pool
from arq.connections import RedisSettings
from app.workers.arq_worker import host, port, database

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await redis_client.connect()
    
    FastAPICache.init(RedisBackend(redis_client.client), prefix="fastapi-cache")
    
    # Initialize ARQ pool
    app.state.arq_pool = await create_pool(RedisSettings(host=host, port=port, database=database))
    
    # Start the reservation cleanup background task
    cleanup_task = asyncio.create_task(cleanup_expired_reservations_loop())
    
    client = None
    try:
        client = await get_es_client()
        logger.info("Elasticsearch client initialized successfully")
        
        if client is not None:
            await create_product_index(client)
            await bulk_index_products(client)
    except Exception as e:
        logger.warning(
            f"Failed to initialize Elasticsearch client or index products: {e}. App will continue without ES."
        )
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
        
    if hasattr(app.state, "arq_pool"):
        await app.state.arq_pool.close()
        
    await redis_client.close()
    await close_es_client()


class RootResponse(BaseModel):
    message: str


app = FastAPI(
    lifespan=lifespan,
    title="E-Commerce Backend API",
    description="RESTful API for managing the product catalog, user authentication, shopping carts, and order processing for the online store.",
    version="1.0.0",
    contact={
        "name": "Yonas Mekonnen",
        "email": "myonas886@gmail.com",
        "url": "https://yonas-mekonnen-portfolio.vercel.app/",
    },
    license_info={
        "name": "MIT",
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
        {
            "name": "reviews",
            "description": "Write and retrieve product reviews.",
        },
        {
            "name": "payment",
            "description": "Stripe payment intent creation and webhook processing.",
        },
    ],
    root_path="/api/v1",
    servers=[],
    docs_url="/docs",
    redoc_url="/redoc",
)

# Global middlewares (Order matters! The last added wraps the inner app first)
# Request logger is outermost
app.add_middleware(LoggingMiddleware)

# Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS — must be added before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Idempotency-Key", "X-Refresh-Token"],
)

app.add_middleware(LoggingMiddleware)

Instrumentator().instrument(app).expose(app)

import sys
if "pytest" not in sys.modules:
    # Configure OpenTelemetry
    resource = Resource(attributes={
        "service.name": "fastapi-app"
    })

    trace.set_tracer_provider(TracerProvider(resource=resource))
    tracer = trace.get_tracer(__name__)

    otlp_exporter = OTLPSpanExporter(endpoint="http://tempo:4317", insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    FastAPIInstrumentor.instrument_app(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(IdempotentResponseException)
async def idempotency_exception_handler(request, exc: IdempotentResponseException):
    return JSONResponse(status_code=exc.status_code, content=exc.content)


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
        content={"detail": f"Please try again later. {exc}"},
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



