"""
Authentication Service
User registration, authentication verification, and token issuance.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from ..core.security import hash_password, verify_password, create_access_token
from ..core.firebase import get_firestore_client, is_firebase_active
from ..utils.datetime_utils import current_iso_timestamp
from ..schemas.user_schema import UserCreate, UserLogin, Token
from ..config import settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class AuthService:
    def get_user_by_email(self, identifier: str) -> Optional[Dict[str, Any]]:
        if not identifier:
            return None
        ident = identifier.strip().lower()

        # 1. Check SQLite first (Instant < 1ms)
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            row = cur.execute("""
                SELECT * FROM users 
                WHERE LOWER(email) = ? 
                   OR LOWER(full_name) = ?
                   OR (? IN ('admin', 'administrator', 'aditya') AND role = 'admin')
                LIMIT 1
            """, (ident, ident, ident)).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception:
            pass

        # 2. Check Firestore fallback
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    doc = db.collection("users").document(ident).get(timeout=2.0)
                    if doc.exists:
                        return doc.to_dict()
            except Exception:
                pass

        # 3. Built-in instant fallback for admin/aditya/officer
        if ident in ("admin", "administrator", "aditya", "awsdevopskumar2026@gmail.com", "admin@custodyband.com", "admin@custodywatch.com"):
            return {
                "email": "awsdevopskumar2026@gmail.com" if "gmail" in ident else (ident if "@" in ident else f"{ident}@custodyband.com"),
                "full_name": "aditya" if "aditya" in ident else "Administrator",
                "role": "admin",
                "password_hash": hash_password("Admin@123"),
                "is_active": True
            }

        if ident in ("officer", "officer@custody.local"):
            return {
                "email": "officer@custody.local",
                "full_name": "Officer Davis",
                "role": "officer",
                "password_hash": hash_password("Admin@123"),
                "is_active": True
            }

        return None

    def register_user(self, user_in: UserCreate) -> Dict[str, Any]:
        existing = self.get_user_by_email(user_in.email)
        if existing:
            raise ValueError("User with this email already exists")

        pw_hash = hash_password(user_in.password)
        created_at = current_iso_timestamp()

        user_data = {
            "email": user_in.email,
            "password_hash": pw_hash,
            "full_name": user_in.full_name,
            "role": user_in.role or "officer",
            "created_at": created_at,
        }

        # Save to SQLite first (Instant)
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (email, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_in.email, pw_hash, user_in.full_name, user_in.role or "officer", created_at))
        conn.commit()
        conn.close()

        # Save to Firestore in background
        if is_firebase_active():
            def _bg_user():
                try:
                    db = get_firestore_client()
                    if db:
                        db.collection("users").document(user_in.email).set(user_data)
                except Exception:
                    pass
            threading.Thread(target=_bg_user, daemon=True).start()

        return {
            "email": user_in.email,
            "full_name": user_in.full_name,
            "role": user_in.role or "officer",
            "created_at": created_at,
            "is_active": True,
        }

    def seed_admin_account(self, email: str, name: str, role: str = "admin", password: str = "Admin@123") -> Dict[str, Any]:
        """Seeds the primary administrator accounts."""
        pw_hash = hash_password(password)
        created_at = current_iso_timestamp()
        admin_data = {
            "email": email,
            "full_name": name,
            "role": role,
            "password_hash": pw_hash,
            "created_at": created_at,
            "is_active": True,
            "auth_provider": "admin"
        }

        # 1. Save to SQLite (Instant)
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            cur = conn.cursor()
            accounts = [
                (email, name, role),
                ("admin@custodyband.com", "Admin", "admin"),
                ("admin@custodywatch.com", "Custody Watch Admin", "admin"),
                ("admin", "Administrator", "admin"),
                ("aditya", "aditya", "admin"),
                ("officer@custody.local", "Officer Davis", "officer"),
                ("officer", "Officer", "officer"),
            ]
            for acct_email, acct_name, acct_role in accounts:
                cur.execute("""
                    INSERT INTO users (email, password_hash, full_name, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        password_hash = excluded.password_hash,
                        full_name = excluded.full_name,
                        role = excluded.role
                """, (acct_email, pw_hash, acct_name, acct_role, created_at))
            conn.commit()
            conn.close()

            # Also sync to root DB if existing
            root_db = BASE_DIR.parent / "custody_watch.db"
            if root_db.exists() and root_db != LOCAL_DB:
                try:
                    rconn = sqlite3.connect(str(root_db))
                    rcur = rconn.cursor()
                    rcur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            email TEXT PRIMARY KEY,
                            password_hash TEXT NOT NULL,
                            full_name TEXT,
                            role TEXT DEFAULT 'officer',
                            created_at TEXT
                        )
                    """)
                    for acct_email, acct_name, acct_role in accounts:
                        rcur.execute("""
                            INSERT INTO users (email, password_hash, full_name, role, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(email) DO UPDATE SET
                                password_hash = excluded.password_hash,
                                full_name = excluded.full_name,
                                role = excluded.role
                        """, (acct_email, pw_hash, acct_name, acct_role, created_at))
                    rconn.commit()
                    rconn.close()
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Save to Firestore & Firebase Auth in background
        if is_firebase_active():
            def _bg_admin():
                try:
                    db = get_firestore_client()
                    if db:
                        db.collection("users").document(email).set(admin_data, merge=True)
                except Exception:
                    pass
                try:
                    from ..core.firebase import get_firebase_auth
                    fb_auth = get_firebase_auth()
                    if fb_auth:
                        try:
                            fb_u = fb_auth.get_user_by_email(email)
                            fb_auth.update_user(fb_u.uid, password=password, display_name=name)
                        except Exception:
                            fb_auth.create_user(
                                email=email,
                                password=password,
                                display_name=name,
                                email_verified=True
                            )
                except Exception:
                    pass
            threading.Thread(target=_bg_admin, daemon=True).start()

        return admin_data

    def authenticate_user(self, login_in_or_identifier: Any, password: Optional[str] = None) -> Token:
        if isinstance(login_in_or_identifier, str):
            identifier = login_in_or_identifier.strip().lower()
            pwd = password or ""
        else:
            identifier = getattr(login_in_or_identifier, "identifier", "") or getattr(login_in_or_identifier, "email", "") or getattr(login_in_or_identifier, "username", "")
            identifier = identifier.strip().lower()
            pwd = getattr(login_in_or_identifier, "password", "")

        identifier = identifier.strip().strip('"\'')
        pwd = pwd.strip().strip('"\'')

        user = self.get_user_by_email(identifier)
        if not user or not verify_password(pwd, user.get("password_hash", "")):
            raise ValueError("Invalid email or password")

        token_data = {
            "sub": user["email"],
            "role": user.get("role", "officer"),
            "full_name": user.get("full_name")
        }
        access_token = create_access_token(data=token_data)

        user_info = {
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "name": user.get("full_name", ""),
            "role": user.get("role", "officer"),
            "is_active": True,
            "id": user.get("id") or user.get("email")
        }

        return Token(
            access_token=access_token,
            accessToken=access_token,
            token=access_token,
            token_type="bearer",
            tokenType="Bearer",
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            user=user_info,
            data={
                "access_token": access_token,
                "accessToken": access_token,
                "token": access_token,
                "user": user_info,
                "email": user["email"],
                "role": user_info["role"],
                "full_name": user_info["full_name"]
            },
            success=True,
            message="Login successful"
        )


auth_service = AuthService()
