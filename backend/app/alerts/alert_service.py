"""
Alert Management Service
Incident lifecycle management: ingestion, officer acknowledgment, and resolution.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..core.firebase import get_firestore_client, is_firebase_active
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class IncidentAlertService:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp TEXT,
                alert_type TEXT,
                message TEXT,
                latitude REAL,
                longitude REAL,
                status TEXT DEFAULT 'NEW',
                acknowledged_by TEXT,
                resolved_by TEXT,
                notes TEXT
            )
        """)
        # Ensure migration columns exist
        existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(alerts)").fetchall()]
        for col in ["acknowledged_by", "resolved_by", "notes"]:
            if col not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE alerts ADD COLUMN {col} TEXT")
                except Exception:
                    pass
        conn.commit()
        conn.close()

    def list_alerts(
        self,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        query = "SELECT * FROM alerts WHERE 1=1"
        params = []
        if status and isinstance(status, str):
            query += " AND status = ?"
            params.append(status.upper())
        if alert_type and isinstance(alert_type, str):
            query += " AND alert_type = ?"
            params.append(alert_type.upper())
        if device_id and isinstance(device_id, str):
            query += " AND device_id = ?"
            params.append(device_id)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = cur.execute(query, params).fetchall()
        conn.close()
        formatted = []
        for r in rows:
            d = dict(r)
            d.setdefault("imei", d.get("device_id"))
            d.setdefault("device", d.get("device_id"))
            d.setdefault("date", d.get("timestamp"))
            d.setdefault("created_at", d.get("timestamp"))
            d.setdefault("type", d.get("alert_type"))
            formatted.append(d)
        return formatted

    def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d.setdefault("imei", d.get("device_id"))
        d.setdefault("device", d.get("device_id"))
        d.setdefault("date", d.get("timestamp"))
        d.setdefault("created_at", d.get("timestamp"))
        d.setdefault("type", d.get("alert_type"))
        d.setdefault("severity", "critical" if d.get("alert_type") == "SOS" else "warning")
        return d

    def acknowledge_alert(self, alert_id: int, officer_email: str, notes: Optional[str] = None) -> Dict[str, Any]:
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            UPDATE alerts SET status = 'ACKNOWLEDGED', acknowledged_by = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        """, (officer_email, notes, alert_id))
        conn.commit()
        conn.close()
        return self.get_alert(alert_id) or {}

    def resolve_alert(self, alert_id: int, officer_email: str, resolution_notes: str) -> Dict[str, Any]:
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            UPDATE alerts SET status = 'RESOLVED', resolved_by = ?, notes = ?
            WHERE id = ?
        """, (officer_email, resolution_notes, alert_id))
        conn.commit()
        conn.close()
        return self.get_alert(alert_id) or {}


incident_alert_service = IncidentAlertService()

