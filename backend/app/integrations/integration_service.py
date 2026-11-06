"""
External Integrations & Webhook Service
Dispatches security event webhooks to police CAD / dispatch networks and verifies cloud connections.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..core.firebase import is_firebase_active
from ..config import settings
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class IntegrationService:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_url TEXT NOT NULL,
                events TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def list_webhooks(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM webhooks ORDER BY id DESC").fetchall()
        res = [dict(r) for r in rows]
        conn.close()
        return res

    def register_webhook(self, name: str, target_url: str, events: str = "ALL") -> Dict[str, Any]:
        ts = current_iso_timestamp()
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO webhooks (name, target_url, events, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
        """, (name, target_url, events, ts))
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": new_id,
            "name": name,
            "target_url": target_url,
            "events": events,
            "created_at": ts,
            "is_active": True
        }

    def get_system_integrations_status(self) -> Dict[str, Any]:
        """Health status of external platform connectors."""
        webhooks = self.list_webhooks()
        return {
            "firebase": {
                "project_id": settings.FIREBASE_PROJECT_ID,
                "connected": is_firebase_active(),
                "credentials_file": settings.FIREBASE_CREDENTIALS_PATH
            },
            "cellular_hardware_receiver": {
                "public_ip": settings.PUBLIC_SERVER_IP,
                "target_port": settings.TCP_PORT,
                "protocol": "TCP & UDP (Huaten C05)"
            },
            "webhooks": {
                "registered_endpoints": len(webhooks),
                "active_webhooks": len([w for w in webhooks if w.get("is_active")])
            }
        }


integration_service = IntegrationService()

