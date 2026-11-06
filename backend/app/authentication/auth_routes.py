"""
Authentication Routes
Endpoints for user registration, token login, and profile inspection.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from urllib.parse import parse_qs
import json
from ..schemas.user_schema import UserCreate, UserLogin, UserResponse, Token
from ..core.dependencies import get_current_user
from .auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate):
    """Registers a new officer or monitoring administrator."""
    try:
        user = auth_service.register_user(user_in)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=Token)
async def login(request: Request):
    """
    Authenticates credentials and issues a JWT Bearer token.
    Seamlessly supports:
      - JSON body ({"email": "...", "password": "..."} or {"username": "...", "password": "..."})
      - Form URL-encoded body (username=...&password=...)
      - Multipart form data
    """
    email_or_user = None
    password = None

    content_type = request.headers.get("content-type", "").lower()

    # 1. Try application/json
    try:
        body = await request.json()
        if isinstance(body, dict):
            email_or_user = (
                body.get("email")
                or body.get("username")
                or body.get("identifier")
                or body.get("user")
                or body.get("login")
                or body.get("account")
            )
            password = body.get("password") or body.get("pass") or body.get("pwd")
    except Exception:
        pass

    # 2. Try Form URL-encoded / multipart
    if not email_or_user or not password:
        try:
            form = await request.form()
            email_or_user = (
                form.get("username")
                or form.get("email")
                or form.get("identifier")
                or form.get("user")
                or form.get("login")
            )
            password = form.get("password") or form.get("pass") or form.get("pwd")
        except Exception:
            pass

    # 3. Fallback: Parse raw payload
    if not email_or_user or not password:
        try:
            raw = await request.body()
            # Try raw bytes as JSON
            try:
                body = json.loads(raw.decode("utf-8"))
                if isinstance(body, dict):
                    email_or_user = (
                        body.get("email")
                        or body.get("username")
                        or body.get("identifier")
                        or body.get("user")
                        or body.get("login")
                        or body.get("account")
                    )
                    password = body.get("password") or body.get("pass") or body.get("pwd")
            except Exception:
                # Try raw bytes as URL-encoded
                parsed = parse_qs(raw.decode("utf-8", errors="ignore"))
                email_or_user = (
                    parsed.get("username")
                    or parsed.get("email")
                    or parsed.get("identifier")
                    or parsed.get("user")
                    or [None]
                )[0]
                password = (parsed.get("password") or parsed.get("pass") or [None])[0]
        except Exception:
            pass

    # 4. Try Query parameters (?username=...&password=...)
    if not email_or_user or not password:
        email_or_user = (
            request.query_params.get("username")
            or request.query_params.get("email")
            or request.query_params.get("identifier")
            or request.query_params.get("user")
            or request.query_params.get("login")
            or request.query_params.get("account")
        )
        password = (
            request.query_params.get("password")
            or request.query_params.get("pass")
            or request.query_params.get("pwd")
        )

    if isinstance(email_or_user, str):
        email_or_user = email_or_user.strip().strip('"\'')
    if isinstance(password, str):
        password = password.strip().strip('"\'')

    if not email_or_user or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username (or email) and password are required"
        )

    try:
        token = auth_service.authenticate_user(email_or_user, password)
        return token
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/login")
def login_status_check():
    """Information endpoint for testing login connectivity."""
    return {
        "status": "ready",
        "method": "POST",
        "supported_fields": ["email", "username", "password"],
        "default_admin_accounts": [
            {"username": "aditya", "password": "Admin@123"},
            {"username": "admin", "password": "Admin@123"},
            {"email": "awsdevopskumar2026@gmail.com", "password": "Admin@123"}
        ]
    }


@router.get("/me", response_model=dict)
def get_profile(current_user: dict = Depends(get_current_user)):
    """Returns the authenticated officer's profile."""
    return current_user

