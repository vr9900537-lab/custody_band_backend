"""
FastAPI Application Entry Point
Initializes HTTP REST API, connects Firebase, seeds admin user, and launches the TCP/UDP Watch Receiver in background.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .utils.logger import app_logger
from .core.firebase import init_firebase, is_firebase_active
from .receiver.tcp_server import start_receiver_background, stop_receiver
from .authentication.auth_routes import router as auth_router
from .authentication.auth_service import auth_service
from .dashboard.dashboard_routes import router as dashboard_router
from .devices.device_routes import router as devices_router
from .gps.gps_routes import router as gps_router

# 11 Feature Modules
from .accounts.account_routes import router as accounts_router
from .monitoring.monitoring_routes import router as monitoring_router
from .playback.playback_routes import router as playback_router
from .geofences.geofence_routes import router as geofences_router
from .commands.command_routes import router as commands_router
from .alerts.alert_routes import router as alerts_router
from .statistics.statistics_routes import router as statistics_router
from .health_data.health_routes import router as health_data_router
from .roles.role_routes import router as roles_router
from .exports.export_routes import router as exports_router
from .integrations.integration_routes import router as integrations_router
from .custody.custody_routes import router as custody_router
from .journeys.journey_routes import router as journey_router

from .services.device_service import device_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: starts servers and database connections."""
    app_logger.info("=" * 60)
    app_logger.info(f"Starting {settings.PROJECT_NAME} (Env: {settings.ENVIRONMENT})")
    app_logger.info(f"Firebase Project: {settings.FIREBASE_PROJECT_ID}")
    app_logger.info(f"Public Endpoint: {settings.PUBLIC_SERVER_IP}:{settings.TCP_PORT}")
    app_logger.info("=" * 60)

    # 1. Initialize Firebase (Firestore & Auth)
    init_firebase()

    # 2. Seed Admin User (Aditya / awsdevopskumar2026@gmail.com)
    try:
        auth_service.seed_admin_account(
            email=settings.ADMIN_EMAIL,
            name=settings.ADMIN_NAME,
            role=settings.ADMIN_ROLE,
            password=getattr(settings, "ADMIN_PASSWORD", "Admin@123")
        )
        app_logger.info(f"Admin account registered: {settings.ADMIN_EMAIL} ({settings.ADMIN_NAME})")
    except Exception as e:
        app_logger.warning(f"Admin account seeding note: {e}")

    # 3. Register default watch only if not already registered
    try:
        if not device_service.get_device(settings.DEFAULT_WATCH_IMEI):
            device_service.register_device({
                "device_id": settings.DEFAULT_WATCH_IMEI,
                "maker": settings.DEFAULT_MANUFACTURER,
                "wearer_name": "Custody Subject",
                "case_number": "CASE-2026-001"
            })
    except Exception:
        pass

    # 4. Start background TCP/UDP receiver for Huaten C05 Watch
    start_receiver_background()

    yield

    app_logger.info(f"Shutting down {settings.PROJECT_NAME}")
    stop_receiver()


# FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API and Telemetry Receiver for Huaten C05 4G GPS Custody Watch with Firebase Integration",
    version="1.0.0",
    lifespan=lifespan
)

# Robust Cross-Origin Resource Sharing (CORS) Configuration
# Allows requests from localhost, local Wi-Fi IPs (192.168.x.x), and remote clients with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def cors_and_headers_middleware(request: Request, call_next):
    """
    Guarantees that every HTTP response (including 401 Unauthorized, 422, 500,
    and OPTIONS preflight requests) returns the proper CORS headers so browsers
    running on separate laptops across Wi-Fi never block requests.
    """
    origin = request.headers.get("origin") or "*"

    if request.method == "OPTIONS":
        response = JSONResponse(
            content={"status": "ok", "message": "Preflight accepted"},
            status_code=200
        )
    else:
        try:
            response = await call_next(request)
        except Exception as exc:
            app_logger.error(f"Global error on {request.method} {request.url.path}: {exc}", exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={"detail": str(exc), "path": request.url.path, "error": type(exc).__name__}
            )

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        resp = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "path": request.url.path}
        )
    else:
        app_logger.error(f"Global error on {request.method} {request.url.path}: {exc}", exc_info=True)
        resp = JSONResponse(
            status_code=500,
            content={"detail": str(exc), "path": request.url.path, "error": type(exc).__name__}
        )
    origin = request.headers.get("origin") or "*"
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


# -----------------------------------------------------------------------------
# Router Registrations across multiple prefix conventions:
# 1. /api/v1 (standard documentation prefix)
# 2. /api    (common frontend baseUrl)
# 3. ""      (root endpoints /login, /devices, /dashboard, etc.)
# -----------------------------------------------------------------------------
ROUTERS = [
    auth_router,
    dashboard_router,
    devices_router,
    gps_router,
    accounts_router,
    monitoring_router,
    playback_router,
    geofences_router,
    commands_router,
    alerts_router,
    statistics_router,
    health_data_router,
    roles_router,
    exports_router,
    integrations_router,
    custody_router,
    journey_router,
]

for router in ROUTERS:
    # 1. Standard /api/v1 (in Swagger)
    app.include_router(router, prefix=settings.API_V1_STR)
    # 2. Common frontend /api (without v1)
    app.include_router(router, prefix="/api", include_in_schema=False)
    # 3. Direct root aliases
    app.include_router(router, prefix="", include_in_schema=False)


from .authentication.auth_routes import login as direct_login_handler, login_status_check
from .core.dependencies import get_current_user

# Direct Universal Login Aliases (POST)
@app.post("/admin/login", include_in_schema=False)
@app.post("/login", include_in_schema=False)
@app.post("/token", include_in_schema=False)
@app.post("/api/login", include_in_schema=False)
@app.post("/api/admin/login", include_in_schema=False)
@app.post("/api/token", include_in_schema=False)
@app.post("/api/auth/login", include_in_schema=False)
@app.post("/api/auth/token", include_in_schema=False)
@app.post(f"{settings.API_V1_STR}/login", include_in_schema=False)
@app.post(f"{settings.API_V1_STR}/admin/login", include_in_schema=False)
@app.post(f"{settings.API_V1_STR}/token", include_in_schema=False)
@app.post(f"{settings.API_V1_STR}/auth/token", include_in_schema=False)
async def direct_login_alias(request: Request):
    return await direct_login_handler(request)


# Universal Login Info & Probe Aliases (GET)
@app.get("/login", include_in_schema=False)
@app.get("/admin/login", include_in_schema=False)
@app.get("/token", include_in_schema=False)
@app.get("/api/login", include_in_schema=False)
@app.get("/api/auth/login", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/login", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/auth/login", include_in_schema=False)
def direct_login_get_alias():
    return login_status_check()


# Universal Profile Aliases (/me, /profile)
@app.get("/me", include_in_schema=False)
@app.get("/profile", include_in_schema=False)
@app.get("/auth/me", include_in_schema=False)
@app.get("/api/me", include_in_schema=False)
@app.get("/api/profile", include_in_schema=False)
@app.get("/api/auth/me", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/me", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/profile", include_in_schema=False)
async def direct_profile_alias(current_user: dict = Depends(get_current_user)):
    return current_user

from .gps.gps_routes import ingest_gps_telemetry

@app.post("/api/v1/ingest", include_in_schema=False)
@app.post("/ingest", include_in_schema=False)
async def generic_ingest_alias(request: Request):
    return await ingest_gps_telemetry(request)


# Valid transparent 16x16 .ico binary for clean browser icon rendering
FAVICON_BYTES = (
    b"\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00h\x04\x00\x00"
    b"\x16\x00\x00\x00(\x00\x00\x00\x10\x00\x00\x00 \x00\x00\x00\x01\x00"
    b"\x20\x00\x00\x00\x00\x00\x00\x04\x00\x00\x13\x0b\x00\x00\x13\x0b\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 1024
)


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/api/favicon.ico", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/favicon.ico", include_in_schema=False)
def favicon():
    """Serves valid 200 OK favicon to cleanly satisfy browser requests."""
    return Response(content=FAVICON_BYTES, media_type="image/x-icon", status_code=200)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "firebase_project": settings.FIREBASE_PROJECT_ID,
        "admin_email": settings.ADMIN_EMAIL,
        "api_docs": "/docs",
        "tcp_receiver": f"{settings.TCP_HOST}:{settings.TCP_PORT}",
        "firebase_active": is_firebase_active(),
        "wifi_host_ip": "192.168.10.91",
        "frontend_api_base_url": "http://192.168.10.91:8000",
        "login_endpoint": "http://192.168.10.91:8000/api/v1/auth/login"
    }


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"], include_in_schema=False)
def health_check():
    return {
        "status": "healthy",
        "firebase_project": settings.FIREBASE_PROJECT_ID,
        "database": "firebase" if is_firebase_active() else "sqlite_local",
        "receiver_port": settings.TCP_PORT
    }


@app.get("/health/ready", tags=["Health"])
@app.get("/ready", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/health/ready", tags=["Health"], include_in_schema=False)
def readiness_check():
    """Kubernetes / Frontend readiness probe."""
    return {
        "status": "ready",
        "ready": True,
        "service": settings.PROJECT_NAME,
        "database": "firebase" if is_firebase_active() else "sqlite_local",
        "firebase_project": settings.FIREBASE_PROJECT_ID,
        "receiver_port": settings.TCP_PORT
    }


@app.get("/health/live", tags=["Health"])
@app.get("/live", include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/health/live", tags=["Health"], include_in_schema=False)
def liveness_check():
    """Kubernetes / Frontend liveness probe."""
    return {
        "status": "alive",
        "live": True,
        "service": settings.PROJECT_NAME
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
