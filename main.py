# Essential imports
import time
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from routers import auth, users, products, categories, cart, orders, admin_products,\
    admin_orders, admin_users, admin_categories, addresses, webhooks
from contextlib import asynccontextmanager
from core.redis_client import redis_client
import redis.asyncio as aioredis
from core.celery_app import celery_app

# Import all models for SQLAlchemy relationship resolution

# Rate limiter imports
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from middleware.rate_limiter import limiter

# Logging imports
from core.logging_config import setup_logging, get_logger
from middleware import RequestIDMiddleware, get_request_id
from core.config import settings
from fastapi.responses import JSONResponse
from utils.deps import db_dependency
from sqlalchemy import text

# CORS imports
from fastapi.middleware.cors import CORSMiddleware

# Initialize logging
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR
)

logger = get_logger(__name__)

# Lifecycle events logging 
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to Redis...")
    await redis_client.connect()

    if settings.ENV == "production" and not limiter.enabled:
        raise RuntimeError(
            "CRITICAL: Rate limiter is disabled in production! "
            "Check ENV configuration."
        )
    
    if settings.ENV != "development" and not settings.STRIPE_SECRET_KEY.startswith("sk_test_"):
        logger.critical("Stripe live key detected, aborting startup")
        raise RuntimeError("CRITICAL: Stripe live keys are not allowed in this codebase.")

    logger.info("Application startup complete", extra={"event": "startup"})
    yield
    logger.info("Disconnecting from Redis...")
    await redis_client.disconnect()
    logger.info("Application shutting down", extra={"event": "shutdown"})


app = FastAPI(
    title="E-Commerce API",
    description="Backend API for e-commerce platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,       # frontend URL
    allow_credentials=True,                    # Allow auth headers/cookies
    allow_methods=["*"],                       # All HTTP methods
    allow_headers=["Authorization", "Content-Type"],                       # All headers
)


# HTTP Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests with method, path, status code, and duration.
    
    Why middleware?
    - Automatic logging for every endpoint
    - No need to manually log in each route
    - Captures timing information
    """
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Log the request
    logger.info(
        f'{client_ip} - "{request.method} {request.url.path} HTTP/1.1" {response.status_code}',
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration, 2),
            "client_ip": client_ip
            # Note: request_id is automatically added by RequestIDMiddleware
        }
    )
    
    return response


# Add request ID middleware
app.add_middleware(RequestIDMiddleware)



# Health check
@app.get("/health")
async def health_check(db: db_dependency):
    """Readiness probe — verifies PostgreSQL and Redis are reachable."""
    health = {"postgres": "ok", "redis": "ok", "celery_broker": "ok"}
    failed = False

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        health["postgres"] = "unavailable"
        failed = True

    try:
        await redis_client.redis.ping()
    except Exception:
        health["redis"] = "unavailable"
        failed = True

    try:
        broker_redis = aioredis.from_url(settings.CELERY_BROKER_URL)
        await broker_redis.ping()
        await broker_redis.aclose()
    except Exception:
        health["celery_broker"] = "unavailable"
        failed = True

    if failed:
        logger.error("Health check failed", extra=health)
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=health)

    logger.info("Health check passed", extra=health)
    return health


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and log them.
    
    Why?
    - Prevents silent failures
    - Logs full context (path, method, error type, stack trace)
    - Returns user-friendly error without exposing internals
    """
    # Skip if it's an HTTPException or validation error (FastAPI handles these)
    if isinstance(exc, (HTTPException, RequestValidationError)):
        raise

    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__
        },
        exc_info=True  # Include full stack trace
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )



# Including routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin_products.router)
app.include_router(admin_orders.router)
app.include_router(admin_users.router)
app.include_router(admin_categories.router)
app.include_router(addresses.router)
app.include_router(webhooks.router)


# Add rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

