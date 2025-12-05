from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.init_routes import init_routes
from app.api.v1.routes import cart, category, healthcheck, product, user
from app.core.elastic_config import close_es_client, get_es_client
from app.core.logger import logger

from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# from app.core.otel_config import setup_otel
from app.core.redis import redis_client
from app.middleware.request_logger import LoggingMiddleware
from app.utils.es_utils import bulk_index_products, create_product_index
from app.utils.seed import seed_product


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # setup_otel()
    await redis_client.connect()
    try:
        client = await get_es_client()
        logger.info("Elasticsearch client initialized successfully")
    except Exception as e:
        logger.warning(
            f"Failed to initialize Elasticsearch client: {e}. App will continue without ES."
        )
    await create_product_index(client)
    await bulk_index_products(client)
    yield
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
            "name": "revewies",
            "description": "write review and get user reviews",
        },
        {
            "name": "payment",
            "description": "process payment",
        },
    ],
    root_path="/api/v1",
    servers=[],
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(LoggingMiddleware)

Instrumentator().instrument(app).expose(app)

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


# seed_product()
# seed_product()
# seed_product()
