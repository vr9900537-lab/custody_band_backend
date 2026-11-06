"""
Geofence Security Service
Manages perimeter boundaries and executes automated violation checks.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..geofences.geofence_schemas import GeofenceCreate, GeofenceUpdate
from ..services.gps_service import gps_service
from ..services.alert_service import alert_service
from ..core.firebase import get_firestore_client, is_firebase_active
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class GeofenceService:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS geofences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                fence_type TEXT NOT NULL,
                center_latitude REAL NOT NULL,
                center_longitude REAL NOT NULL,
                radius_meters REAL NOT NULL,
                assigned_device_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def list_geofences(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM geofences ORDER BY id DESC").fetchall()
        res = [dict(r) for r in rows]
        conn.close()
        return res

    def get_geofence(self, geofence_id: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM geofences WHERE id = ?", (geofence_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create_geofence(self, geo_in: GeofenceCreate) -> Dict[str, Any]:
        created_at = current_iso_timestamp()
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO geofences (name, fence_type, center_latitude, center_longitude, radius_meters, assigned_device_id, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            geo_in.name, geo_in.fence_type.upper(), geo_in.center_latitude,
            geo_in.center_longitude, geo_in.radius_meters, geo_in.assigned_device_id,
            1 if geo_in.is_active else 0, created_at
        ))
        new_id = cur.lastrowid
        conn.commit()
        conn.close()

        record = self.get_geofence(new_id) or geo_in.model_dump()
        if is_firebase_active():
            try:
                db = get_firestore_client()
                db.collection("geofences").document(str(new_id)).set(record)
            except Exception:
                pass
        return record

    def delete_geofence(self, geofence_id: int) -> bool:
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("DELETE FROM geofences WHERE id = ?", (geofence_id,))
        rows = cur.rowcount
        conn.commit()
        conn.close()
        return rows > 0

    def check_position_compliance(self, device_id: str, lat: float, lon: float) -> Dict[str, Any]:
        """Validates coordinates against all active fences assigned to device or global."""
        fences = self.list_geofences()
        violations = []

        for f in fences:
            if not f.get("is_active"):
                continue
            assigned = f.get("assigned_device_id")
            if assigned and assigned != device_id:
                continue

            dist = gps_service.calculate_distance_meters(
                lat, lon, f["center_latitude"], f["center_longitude"]
            )
            radius = f["radius_meters"]
            f_type = f["fence_type"].upper()

            is_violation = False
            if f_type == "INCLUSION" and dist > radius:
                is_violation = True
                msg = f"Breach! Left designated inclusion zone '{f['name']}' ({round(dist, 1)}m > {radius}m)"
            elif f_type == "EXCLUSION" and dist <= radius:
                is_violation = True
                msg = f"Breach! Entered prohibited exclusion zone '{f['name']}' ({round(dist, 1)}m <= {radius}m)"

            if is_violation:
                violations.append({
                    "geofence_id": f["id"],
                    "geofence_name": f["name"],
                    "fence_type": f_type,
                    "distance_meters": round(dist, 1),
                    "allowed_radius": radius,
                    "message": msg
                })
                # Trigger critical alert
                alert_service.trigger_alert(
                    device_id=device_id,
                    alert_type="GEOFENCE_BREACH",
                    message=msg,
                    latitude=lat,
                    longitude=lon
                )

        return {
            "device_id": device_id,
            "latitude": lat,
            "longitude": lon,
            "is_compliant": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations
        }


geofence_service = GeofenceService()

