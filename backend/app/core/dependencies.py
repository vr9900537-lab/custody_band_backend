"""
FastAPI Dependencies
Supports authentication via Firebase Auth ID Tokens and custom backend JWTs.
"""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .security import decode_access_token
from .firebase import get_firestore_client, get_firebase_auth, is_firebase_active
from ..config import settings

security_scheme = HTTPBearer(auto_error=False)


def get_db():
    """Dependency for obtaining database client (Firestore or local)."""
    return get_firestore_client()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    Extracts and validates user identity.
    Checks:
    1. Authorization Bearer header
    2. x-access-token / x-auth-token header
    3. Query parameter ?token=... / ?access_token=...
    4. Cookies
    5. Firebase Auth ID Token (if Firebase is active)
    6. Backend custom JWT Bearer token
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        auth_hdr = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
        if auth_hdr:
            token = auth_hdr.split("Bearer ")[-1].strip() if ("Bearer " in auth_hdr or "bearer " in auth_hdr) else auth_hdr.strip()
        elif request.headers.get("x-access-token"):
            token = request.headers.get("x-access-token").strip()
        elif request.headers.get("x-auth-token"):
            token = request.headers.get("x-auth-token").strip()
        elif request.query_params.get("token"):
            token = request.query_params.get("token").strip()
        elif request.query_params.get("access_token"):
            token = request.query_params.get("access_token").strip()
        elif request.cookies.get("token"):
            token = request.cookies.get("token").strip()
        elif request.cookies.get("access_token"):
            token = request.cookies.get("access_token").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Try Firebase Auth verification first
    fb_auth = get_firebase_auth()
    if fb_auth:
        try:
            decoded_firebase = fb_auth.verify_id_token(token)
            email = decoded_firebase.get("email", "")
            role = "admin" if email.lower() == settings.ADMIN_EMAIL.lower() else "officer"
            return {
                "email": email,
                "role": role,
                "user_id": decoded_firebase.get("uid"),
                "auth_provider": "firebase",
                "name": decoded_firebase.get("name", email.split("@")[0])
            }
        except Exception:
            pass

    # 2. Try custom backend JWT
    payload = decode_access_token(token)
    if payload:
        user_email = payload.get("sub", "")
        role = payload.get("role", "admin" if user_email.lower() == settings.ADMIN_EMAIL.lower() else "officer")
        return {
            "email": user_email,
            "role": role,
            "user_id": payload.get("user_id", user_email),
            "auth_provider": "jwt",
            "name": payload.get("full_name", user_email.split("@")[0])
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
