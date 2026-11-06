"""
Account Management Service
CRUD operations and credential updates for monitoring officers and administrators.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..core.security import hash_password, verify_password
from ..core.firebase import get_firestore_client, is_firebase_active
from ..accounts.account_schemas import AccountCreate, AccountUpdate, PasswordChangeRequest
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class AccountService:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password_hash TEXT,
                full_name TEXT,
                role TEXT,
                badge_number TEXT,
                phone_number TEXT,
                department TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def list_accounts(self) -> List[Dict[str, Any]]:
        if is_firebase_active():
            try:
                db = get_firestore_client()
                docs = db.collection("users").stream()
                users = []
                for d in docs:
                    data = d.to_dict()
                    data.pop("password_hash", None)
                    users.append(data)
                if users:
                    return users
            except Exception:
                pass

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT email, full_name, role, badge_number, phone_number, department, is_active, created_at FROM users").fetchall()
        res = [dict(r) for r in rows]
        conn.close()
        return res

    def get_account(self, email: str) -> Optional[Dict[str, Any]]:
        if is_firebase_active():
            try:
                db = get_firestore_client()
                doc = db.collection("users").document(email).get()
                if doc.exists:
                    data = doc.to_dict()
                    data.pop("password_hash", None)
                    return data
            except Exception:
                pass

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT email, full_name, role, badge_number, phone_number, department, is_active, created_at FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_account(self, email: str, update_in: AccountUpdate) -> Dict[str, Any]:
        update_data = {k: v for k, v in update_in.model_dump().items() if v is not None}
        if not update_data:
            return self.get_account(email) or {}

        if is_firebase_active():
            try:
                db = get_firestore_client()
                db.collection("users").document(email).set(update_data, merge=True)
            except Exception:
                pass

        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        fields = [f"{k} = ?" for k in update_data.keys()]
        values = list(update_data.values())
        values.append(email)
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE email = ?", values)
        conn.commit()
        conn.close()

        return self.get_account(email) or {}

    def change_password(self, email: str, pw_req: PasswordChangeRequest) -> bool:
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        row = cur.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            conn.close()
            return False

        stored_hash = row[0]
        if not verify_password(pw_req.current_password, stored_hash):
            conn.close()
            raise ValueError("Current password does not match")

        new_hash = hash_password(pw_req.new_password)
        cur.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, email))
        conn.commit()
        conn.close()

        if is_firebase_active():
            try:
                db = get_firestore_client()
                db.collection("users").document(email).update({"password_hash": new_hash})
            except Exception:
                pass

        return True

    def deactivate_account(self, email: str) -> bool:
        return bool(self.update_account(email, AccountUpdate(is_active=False)))


account_service = AccountService()

