"""
Firestore & Local Persistence Service
Provides abstraction for Firestore with transparent SQLite fallback when offline/unconfigured.
Uses real device telemetry without mock defaults.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..core.firebase import get_firestore_client, is_firebase_active
from ..utils.logger import app_logger
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class FirestoreService:
    def __init__(self):
        self._init_local_db()

    def _init_local_db(self):
        """Prepares local SQLite tables for fallback persistence."""
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                maker TEXT,
                wearer_name TEXT,
                case_number TEXT,
                last_seen TEXT,
                battery INTEGER,
                steps INTEGER,
                heart_rate INTEGER,
                status TEXT,
                last_latitude REAL,
                last_longitude REAL,
                maps_url TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp TEXT,
                gps_valid INTEGER,
                latitude REAL,
                longitude REAL,
                speed_kmh REAL,
                battery INTEGER,
                steps INTEGER,
                maps_url TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp TEXT,
                alert_type TEXT,
                message TEXT,
                latitude REAL,
                longitude REAL,
                status TEXT,
                acknowledged_by TEXT,
                resolved_by TEXT,
                notes TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password_hash TEXT,
                full_name TEXT,
                role TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS journeys (
                journey_id TEXT PRIMARY KEY,
                device_id TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                start_latitude REAL,
                start_longitude REAL,
                end_latitude REAL,
                end_longitude REAL,
                total_distance_km REAL,
                duration_seconds INTEGER,
                duration_formatted TEXT,
                points_count INTEGER,
                route_coordinates_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migration columns for devices
        existing_device_cols = [c[1] for c in cur.execute("PRAGMA table_info(devices)").fetchall()]
        for col in ["heading", "bearing", "course", "speed"]:
            if col not in existing_device_cols:
                try:
                    cur.execute(f"ALTER TABLE devices ADD COLUMN {col} REAL DEFAULT 0.0")
                except Exception:
                    pass
        for col in ["is_charging", "charging"]:
            if col not in existing_device_cols:
                try:
                    cur.execute(f"ALTER TABLE devices ADD COLUMN {col} INTEGER DEFAULT 0")
                except Exception:
                    pass
        for col in ["last_valid_gps_time", "gps_status", "satellites", "gsm_signal"]:
            if col not in existing_device_cols:
                try:
                    cur.execute(f"ALTER TABLE devices ADD COLUMN {col} TEXT")
                except Exception:
                    pass
        for col in ["gps_valid", "gps_fix", "gps_locked"]:
            if col not in existing_device_cols:
                try:
                    cur.execute(f"ALTER TABLE devices ADD COLUMN {col} INTEGER DEFAULT 0")
                except Exception:
                    pass

        # Migration columns for telemetry
        existing_telem_cols = [c[1] for c in cur.execute("PRAGMA table_info(telemetry)").fetchall()]
        for col in ["heading", "bearing", "course"]:
            if col not in existing_telem_cols:
                try:
                    cur.execute(f"ALTER TABLE telemetry ADD COLUMN {col} REAL DEFAULT 0.0")
                except Exception:
                    pass
        for col in ["is_charging", "charging"]:
            if col not in existing_telem_cols:
                try:
                    cur.execute(f"ALTER TABLE telemetry ADD COLUMN {col} INTEGER DEFAULT 0")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    def _enrich_device_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates dynamic status, online state, and GPS status for a device."""
        now_dt = datetime.now(timezone.utc)
        dev_id = str(d.get("device_id") or d.get("id") or "")
        d["id"] = dev_id
        d["device_id"] = dev_id
        d["imei"] = dev_id

        # Calculate ONLINE / OFFLINE from actual last communication timestamp
        last_seen_str = d.get("last_seen")
        is_online = False
        if last_seen_str:
            try:
                dt_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                # Online threshold: 10 minutes (600 seconds)
                if (now_dt - dt_seen).total_seconds() <= 600:
                    is_online = True
            except Exception:
                is_online = d.get("status") in ("ONLINE", "ACTIVE")
        else:
            is_online = d.get("status") in ("ONLINE", "ACTIVE")

        d["online"] = is_online
        d["status"] = "ONLINE" if is_online else "OFFLINE"

        # Coordinates
        lat = d.get("last_latitude") if d.get("last_latitude") is not None else d.get("latitude")
        lon = d.get("last_longitude") if d.get("last_longitude") is not None else d.get("longitude")
        d["last_latitude"] = lat
        d["last_longitude"] = lon
        d["latitude"] = lat
        d["longitude"] = lon
        d["lat"] = lat
        d["lon"] = lon
        d["lng"] = lon

        # GPS Status resolution: GPS Locked, Location Stale, No Fix
        is_gps_valid = bool(d.get("gps_valid", False))
        last_valid_gps_time = d.get("last_valid_gps_time")

        if is_gps_valid and lat is not None and lon is not None:
            if last_valid_gps_time:
                try:
                    dt_gps = datetime.fromisoformat(last_valid_gps_time.replace("Z", "+00:00"))
                    if (now_dt - dt_gps).total_seconds() > 900:  # 15 min stale
                        gps_status = "Location Stale"
                        is_gps_valid = False
                    else:
                        gps_status = "GPS Locked"
                except Exception:
                    gps_status = "GPS Locked"
            else:
                gps_status = "GPS Locked"
        else:
            if last_valid_gps_time and lat is not None and lon is not None:
                try:
                    dt_gps = datetime.fromisoformat(last_valid_gps_time.replace("Z", "+00:00"))
                    if (now_dt - dt_gps).total_seconds() > 900:
                        gps_status = "Location Stale"
                    else:
                        gps_status = "No Fix"
                except Exception:
                    gps_status = "No Fix"
            else:
                gps_status = "No Fix"

        d["gps_valid"] = is_gps_valid
        d["gps_fix"] = is_gps_valid
        d["gps_locked"] = is_gps_valid
        d["gps_status"] = gps_status

        # Battery - use real device battery reading; DO NOT default to 90
        batt = d.get("battery")
        if batt is not None:
            try:
                b_int = int(batt)
                d["battery"] = b_int
                d["battery_level"] = b_int
                d["batteryLevel"] = b_int
                d["battery_percent"] = b_int
                d["battery_pct"] = b_int
                d["charge"] = b_int
                d["battery_status"] = "normal" if b_int > 20 else "low"
            except (ValueError, TypeError):
                pass

        is_chg = bool(d.get("is_charging") or d.get("charging") or False)
        d["is_charging"] = is_chg
        d["charging"] = is_chg
        d["isCharging"] = is_chg
        d["charge_status"] = "charging" if is_chg else "discharging"

        # Direction / Heading
        h = float(d.get("heading") or d.get("bearing") or d.get("course") or d.get("direction_deg") or 0.0)
        d["heading"] = h
        d["bearing"] = h
        d["course"] = h
        d["direction"] = h
        d["direction_deg"] = h
        d["angle"] = h
        d["rotation"] = h

        spd = float(d.get("speed") or d.get("speed_kmh") or 0.0)
        d["speed"] = spd
        d["speed_kmh"] = spd

        return d

    # --- DEVICES ---
    def save_device(self, device_data: Dict[str, Any]):
        """
        Saves device telemetry and state to SQLite and Firebase Firestore.
        Preserves previous valid coordinates and battery readings without mock defaults.
        """
        dev_id = device_data["device_id"]
        batt_val = device_data.get("battery") if device_data.get("battery") is not None else device_data.get("battery_level")
        steps_val = device_data.get("steps")
        is_charging_val = 1 if (device_data.get("is_charging") or device_data.get("charging")) else 0
        heading_val = (
            device_data.get("heading")
            if device_data.get("heading") is not None
            else (device_data.get("bearing") if device_data.get("bearing") is not None else device_data.get("course"))
        )
        speed_val = device_data.get("speed_kmh") if device_data.get("speed_kmh") is not None else device_data.get("speed")
        last_lat = device_data.get("last_latitude")
        last_lon = device_data.get("last_longitude")
        last_valid_gps_time = device_data.get("last_valid_gps_time")
        gps_status = device_data.get("gps_status", "No Fix")

        # 1. Local SQLite Backup
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO devices (
                    device_id, maker, wearer_name, case_number, last_seen,
                    battery, steps, heart_rate, status, last_latitude, last_longitude, maps_url,
                    heading, bearing, course, speed, is_charging, last_valid_gps_time, gps_status, gps_valid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    maker = COALESCE(excluded.maker, devices.maker),
                    wearer_name = COALESCE(excluded.wearer_name, devices.wearer_name),
                    case_number = COALESCE(excluded.case_number, devices.case_number),
                    last_seen = COALESCE(excluded.last_seen, devices.last_seen),
                    battery = CASE 
                        WHEN excluded.battery IS NOT NULL THEN excluded.battery 
                        ELSE devices.battery 
                    END,
                    steps = CASE 
                        WHEN excluded.steps IS NOT NULL THEN excluded.steps 
                        ELSE devices.steps 
                    END,
                    heart_rate = COALESCE(excluded.heart_rate, devices.heart_rate),
                    status = COALESCE(excluded.status, devices.status),
                    last_latitude = COALESCE(excluded.last_latitude, devices.last_latitude),
                    last_longitude = COALESCE(excluded.last_longitude, devices.last_longitude),
                    maps_url = COALESCE(excluded.maps_url, devices.maps_url),
                    heading = COALESCE(excluded.heading, devices.heading),
                    bearing = COALESCE(excluded.bearing, devices.bearing),
                    course = COALESCE(excluded.course, devices.course),
                    speed = COALESCE(excluded.speed, devices.speed),
                    is_charging = COALESCE(excluded.is_charging, devices.is_charging),
                    last_valid_gps_time = COALESCE(excluded.last_valid_gps_time, devices.last_valid_gps_time),
                    gps_status = COALESCE(excluded.gps_status, devices.gps_status),
                    gps_valid = COALESCE(excluded.gps_valid, devices.gps_valid)
            """, (
                dev_id,
                device_data.get("maker"),
                device_data.get("wearer_name"),
                device_data.get("case_number"),
                device_data.get("last_seen"),
                batt_val,
                steps_val,
                device_data.get("heart_rate"),
                device_data.get("status", "ACTIVE"),
                last_lat,
                last_lon,
                device_data.get("maps_url"),
                float(heading_val) if heading_val is not None else None,
                float(heading_val) if heading_val is not None else None,
                float(heading_val) if heading_val is not None else None,
                float(speed_val) if speed_val is not None else None,
                is_charging_val,
                last_valid_gps_time,
                gps_status,
                1 if device_data.get("gps_valid") else 0
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"SQLite save_device error: {e}")

        # 2. Asynchronous Firestore Sync
        if is_firebase_active():
            def _bg_sync():
                try:
                    db = get_firestore_client()
                    if db:
                        h = float(heading_val or 0.0)
                        spd = float(speed_val or 0.0)
                        ts = device_data.get("last_seen") or current_iso_timestamp()
                        is_valid_fix = bool(device_data.get("gps_valid", False))

                        sync_doc: Dict[str, Any] = {
                            **device_data,
                            "heading": h,
                            "bearing": h,
                            "course": h,
                            "direction": h,
                            "direction_deg": h,
                            "angle": h,
                            "rotation": h,
                            "speed": spd,
                            "speed_kmh": spd,
                            "status": device_data.get("status", "ONLINE"),
                            "last_seen": ts,
                            "gps_valid": is_valid_fix,
                            "gps_fix": is_valid_fix,
                            "gps_locked": is_valid_fix,
                            "gps_status": gps_status,
                        }

                        if batt_val is not None:
                            sync_doc["battery"] = batt_val
                            sync_doc["battery_percent"] = batt_val
                            sync_doc["battery_level"] = batt_val
                            sync_doc["charge"] = batt_val

                        # Coordinates
                        if last_lat is not None and last_lon is not None:
                            sync_doc["last_latitude"] = last_lat
                            sync_doc["last_longitude"] = last_lon
                            sync_doc["lat"] = last_lat
                            sync_doc["lon"] = last_lon
                            sync_doc["latitude"] = last_lat
                            sync_doc["longitude"] = last_lon
                            if last_valid_gps_time:
                                sync_doc["last_valid_gps_time"] = last_valid_gps_time

                            sync_doc["latest"] = {
                                "location": {
                                    "lat": last_lat,
                                    "lon": last_lon,
                                    "latitude": last_lat,
                                    "longitude": last_lon,
                                    "direction_deg": h,
                                    "heading": h,
                                    "bearing": h,
                                    "course": h,
                                    "speed_kmh": spd,
                                    "gps_fix": is_valid_fix,
                                    "gps_valid": is_valid_fix,
                                    "gps_locked": is_valid_fix,
                                    "gps_status": gps_status,
                                    "device_id": dev_id,
                                    "gps_time": last_valid_gps_time or ts,
                                    "received_at": ts
                                },
                                "status": {
                                    "device_id": dev_id,
                                    "received_at": ts,
                                    "status": device_data.get("status", "ONLINE")
                                }
                            }
                            if batt_val is not None:
                                sync_doc["latest"]["location"]["battery_percent"] = batt_val
                                sync_doc["latest"]["status"]["battery_percent"] = batt_val

                        db.collection("devices").document(dev_id).set(sync_doc, merge=True)
                except Exception as e:
                    app_logger.error(f"Firestore save_device sync error for {dev_id}: {e}")

            threading.Thread(target=_bg_sync, daemon=True).start()

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Fetches all devices from Firebase Firestore when active;
        falls back to SQLite with explicit logging if Firebase is offline.
        """
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    docs = db.collection("devices").stream(timeout=2.0)
                    devices = []
                    for doc in docs:
                        d = doc.to_dict()
                        d["device_id"] = doc.id
                        devices.append(self._enrich_device_dict(d))
                    if devices:
                        return devices
            except Exception as e:
                app_logger.error(f"Firestore get_devices failed: {e}. Falling back to SQLite.")

        # SQLite fallback
        app_logger.warning("Retrieving devices from local SQLite fallback storage.")
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM devices").fetchall()
        conn.close()
        formatted = []
        for r in rows:
            d = dict(r)
            formatted.append(self._enrich_device_dict(d))
        return formatted

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches single device details from Firestore when active;
        falls back to SQLite with explicit logging if Firebase is offline.
        """
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    doc = db.collection("devices").document(device_id).get(timeout=2.0)
                    if doc.exists:
                        d = doc.to_dict()
                        d["device_id"] = doc.id
                        return self._enrich_device_dict(d)
            except Exception as e:
                app_logger.error(f"Firestore get_device for {device_id} failed: {e}. Falling back to SQLite.")

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            return self._enrich_device_dict(d)
        return None

    def update_device_wearer(self, device_id: str, wearer_name: str, case_number: str):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute(
            "UPDATE devices SET wearer_name = ?, case_number = ? WHERE device_id = ?",
            (wearer_name, case_number, device_id)
        )
        conn.commit()
        conn.close()

        if is_firebase_active():
            def _bg_sync():
                try:
                    db = get_firestore_client()
                    if db:
                        db.collection("devices").document(device_id).set({
                            "wearer_name": wearer_name,
                            "case_number": case_number
                        }, merge=True)
                except Exception as e:
                    app_logger.error(f"Firestore update_device_wearer error: {e}")
            threading.Thread(target=_bg_sync, daemon=True).start()

    # --- TELEMETRY ---
    def save_telemetry(self, data: Dict[str, Any]):
        """
        Saves GPS and sensor telemetry record into SQLite and Firebase history subcollection.
        Never overwrites valid device coordinates with invalid readings.
        """
        dev_id = str(data["device_id"])
        lat = data.get("latitude")
        lon = data.get("longitude")
        is_gps_valid = bool(data.get("gps_valid", False)) and (lat is not None and lon is not None and (lat != 0.0 or lon != 0.0))
        speed_val = data.get("speed_kmh") if data.get("speed_kmh") is not None else data.get("speed")
        bearing_val = (
            data.get("heading")
            if data.get("heading") is not None
            else (data.get("bearing") if data.get("bearing") is not None else data.get("course"))
        )
        batt_val = data.get("battery")

        # 1. Local SQLite
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO telemetry (
                    device_id, timestamp, gps_valid, latitude, longitude,
                    speed_kmh, battery, steps, maps_url, heading, bearing, course
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dev_id,
                data.get("timestamp"),
                1 if is_gps_valid else 0,
                lat if is_gps_valid else None,
                lon if is_gps_valid else None,
                float(speed_val) if speed_val is not None else 0.0,
                batt_val if batt_val is not None else 0,
                data.get("steps", 0),
                data.get("maps_url"),
                float(bearing_val) if bearing_val is not None else 0.0,
                float(bearing_val) if bearing_val is not None else 0.0,
                float(bearing_val) if bearing_val is not None else 0.0
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"SQLite save_telemetry error: {e}")

        # 2. Async Firestore Sync
        if is_firebase_active():
            def _bg_sync():
                try:
                    db = get_firestore_client()
                    if db:
                        h = float(bearing_val or 0.0)
                        spd = float(speed_val or 0.0)
                        ts = data.get("timestamp") or current_iso_timestamp()

                        telemetry_record = {
                            **data,
                            "heading": h,
                            "bearing": h,
                            "course": h,
                            "direction_deg": h,
                            "direction": h,
                            "speed": spd,
                            "speed_kmh": spd,
                            "timestamp": ts,
                            "gps_valid": is_gps_valid,
                            "gps_fix": is_gps_valid,
                            "gps_locked": is_gps_valid,
                            "gps_status": "GPS Locked" if is_gps_valid else "No Fix",
                        }
                        if batt_val is not None:
                            telemetry_record["battery"] = batt_val
                            telemetry_record["battery_percent"] = batt_val

                        # Add to telemetry collection and device history subcollection
                        db.collection("telemetry").add(telemetry_record)
                        db.collection("devices").document(dev_id).collection("history").add(telemetry_record)

                        # Update parent device document
                        gps_status_str = "GPS Locked" if is_gps_valid else "No Fix"
                        dev_update: Dict[str, Any] = {
                            "heading": h,
                            "bearing": h,
                            "course": h,
                            "direction": h,
                            "direction_deg": h,
                            "angle": h,
                            "rotation": h,
                            "speed": spd,
                            "speed_kmh": spd,
                            "status": "ONLINE",
                            "last_seen": ts,
                            "gps_valid": is_gps_valid,
                            "gps_fix": is_gps_valid,
                            "gps_locked": is_gps_valid,
                            "gps_status": gps_status_str,
                        }

                        if batt_val is not None:
                            dev_update["battery"] = batt_val
                            dev_update["battery_percent"] = batt_val
                            dev_update["battery_level"] = batt_val
                            dev_update["charge"] = batt_val

                        # Only update coordinates on parent doc if GPS is genuinely valid
                        if is_gps_valid and lat is not None and lon is not None:
                            dev_update["last_latitude"] = lat
                            dev_update["last_longitude"] = lon
                            dev_update["lat"] = lat
                            dev_update["lon"] = lon
                            dev_update["latitude"] = lat
                            dev_update["longitude"] = lon
                            dev_update["last_valid_gps_time"] = ts
                            dev_update["maps_url"] = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
                            dev_update["latest"] = {
                                "location": {
                                    "lat": lat,
                                    "lon": lon,
                                    "latitude": lat,
                                    "longitude": lon,
                                    "direction_deg": h,
                                    "heading": h,
                                    "bearing": h,
                                    "course": h,
                                    "speed_kmh": spd,
                                    "gps_fix": True,
                                    "gps_valid": True,
                                    "gps_locked": True,
                                    "gps_status": "GPS Locked",
                                    "device_id": dev_id,
                                    "gps_time": ts,
                                    "received_at": ts
                                },
                                "status": {
                                    "device_id": dev_id,
                                    "received_at": ts,
                                    "status": "ONLINE"
                                }
                            }
                            if batt_val is not None:
                                dev_update["latest"]["location"]["battery_percent"] = batt_val
                                dev_update["latest"]["status"]["battery_percent"] = batt_val

                        db.collection("devices").document(dev_id).set(dev_update, merge=True)
                except Exception as e:
                    app_logger.error(f"Firestore save_telemetry sync error: {e}")

            threading.Thread(target=_bg_sync, daemon=True).start()

    def get_telemetry_history(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM telemetry WHERE device_id = ? ORDER BY id DESC LIMIT ?",
            (device_id, limit)
        ).fetchall()
        conn.close()
        formatted = []
        for r in rows:
            d = dict(r)
            d.setdefault("heading", d.get("heading", 0.0))
            d.setdefault("bearing", d.get("heading", 0.0))
            d.setdefault("direction_deg", d.get("heading", 0.0))
            d.setdefault("speed", d.get("speed_kmh", 0.0))
            formatted.append(d)
        return formatted

    # --- ALERTS ---
    def save_alert(self, alert_data: Dict[str, Any]):
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO alerts (
                    device_id, timestamp, alert_type, message, latitude, longitude,
                    status, acknowledged_by, resolved_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_data["device_id"],
                alert_data["timestamp"],
                alert_data["alert_type"],
                alert_data["message"],
                alert_data.get("latitude"),
                alert_data.get("longitude"),
                alert_data.get("status", "NEW"),
                alert_data.get("acknowledged_by"),
                alert_data.get("resolved_by"),
                alert_data.get("notes")
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"SQLite save_alert error: {e}")

        if is_firebase_active():
            def _bg_sync():
                try:
                    db = get_firestore_client()
                    if db:
                        db.collection("alerts").add(alert_data)
                except Exception as e:
                    app_logger.error(f"Firestore save_alert error: {e}")
            threading.Thread(target=_bg_sync, daemon=True).start()

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        formatted = []
        for r in rows:
            d = dict(r)
            d.setdefault("imei", d.get("device_id"))
            d.setdefault("device", d.get("device_id"))
            d.setdefault("date", d.get("timestamp"))
            d.setdefault("created_at", d.get("timestamp"))
            d.setdefault("type", d.get("alert_type"))
            d.setdefault("severity", "warning" if d.get("alert_type") != "SOS" else "critical")
            formatted.append(d)
        return formatted

    # --- JOURNEYS ---
    def save_journey(self, journey_data: Dict[str, Any]):
        """
        Saves journey metadata and route coordinates to SQLite and Firebase Firestore.
        Synchronizes to both top-level 'journeys' and 'devices/{device_id}/journeys'.
        """
        j_id = journey_data["journey_id"]
        dev_id = journey_data["device_id"]
        status = journey_data.get("status", "ACTIVE")
        st = journey_data.get("start_time")
        et = journey_data.get("end_time")

        sl = journey_data.get("start_location") or {}
        el = journey_data.get("end_location") or {}
        s_lat = sl.get("latitude")
        s_lon = sl.get("longitude")
        e_lat = el.get("latitude")
        e_lon = el.get("longitude")

        dist_km = float(journey_data.get("total_distance_km", 0.0))
        dur_sec = int(journey_data.get("duration_seconds", 0))
        dur_fmt = str(journey_data.get("duration_formatted", "00:00:00"))
        pts_count = int(journey_data.get("points_count", len(journey_data.get("route_coordinates", []))))
        route_json = json.dumps(journey_data.get("route_coordinates", []))
        created_at = journey_data.get("created_at") or current_iso_timestamp()
        updated_at = journey_data.get("updated_at") or current_iso_timestamp()

        # 1. Local SQLite Backup
        try:
            conn = sqlite3.connect(str(LOCAL_DB))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO journeys (
                    journey_id, device_id, status, start_time, end_time,
                    start_latitude, start_longitude, end_latitude, end_longitude,
                    total_distance_km, duration_seconds, duration_formatted,
                    points_count, route_coordinates_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(journey_id) DO UPDATE SET
                    status = excluded.status,
                    end_time = excluded.end_time,
                    start_latitude = COALESCE(excluded.start_latitude, journeys.start_latitude),
                    start_longitude = COALESCE(excluded.start_longitude, journeys.start_longitude),
                    end_latitude = COALESCE(excluded.end_latitude, journeys.end_latitude),
                    end_longitude = COALESCE(excluded.end_longitude, journeys.end_longitude),
                    total_distance_km = excluded.total_distance_km,
                    duration_seconds = excluded.duration_seconds,
                    duration_formatted = excluded.duration_formatted,
                    points_count = excluded.points_count,
                    route_coordinates_json = excluded.route_coordinates_json,
                    updated_at = excluded.updated_at
            """, (
                j_id, dev_id, status, st, et,
                s_lat, s_lon, e_lat, e_lon,
                dist_km, dur_sec, dur_fmt,
                pts_count, route_json, created_at, updated_at
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            app_logger.error(f"SQLite save_journey error: {e}")

        # 2. Async Firestore Sync
        if is_firebase_active():
            def _bg_sync():
                try:
                    db = get_firestore_client()
                    if db:
                        sync_payload = {
                            **journey_data,
                            "id": j_id,
                            "journey_id": j_id,
                            "device_id": dev_id,
                            "status": status,
                            "start_time": st,
                            "end_time": et,
                            "total_distance_km": dist_km,
                            "duration_seconds": dur_sec,
                            "duration_formatted": dur_fmt,
                            "points_count": pts_count,
                            "created_at": created_at,
                            "updated_at": updated_at
                        }
                        # Save in top-level collection and device subcollection
                        db.collection("journeys").document(j_id).set(sync_payload, merge=True)
                        db.collection("devices").document(dev_id).collection("journeys").document(j_id).set(sync_payload, merge=True)
                        # Also update active_journey_id on parent device
                        db.collection("devices").document(dev_id).set({
                            "active_journey_id": j_id if status == "ACTIVE" else None
                        }, merge=True)
                except Exception as e:
                    app_logger.error(f"Firestore save_journey error for {j_id}: {e}")

            threading.Thread(target=_bg_sync, daemon=True).start()

    def get_active_journey(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves currently ACTIVE journey for a device."""
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    dev_doc = db.collection("devices").document(device_id).get(timeout=2.0)
                    if dev_doc.exists:
                        active_id = dev_doc.to_dict().get("active_journey_id")
                        if active_id:
                            j_doc = db.collection("journeys").document(active_id).get(timeout=2.0)
                            if j_doc.exists:
                                d = j_doc.to_dict()
                                d["id"] = j_doc.id
                                return d
            except Exception as e:
                app_logger.error(f"Firestore get_active_journey failed: {e}")

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM journeys WHERE device_id = ? AND status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1",
            (device_id,)
        ).fetchone()
        conn.close()
        if row:
            d = dict(row)
            try:
                d["route_coordinates"] = json.loads(d.get("route_coordinates_json") or "[]")
            except Exception:
                d["route_coordinates"] = []
            if d.get("start_latitude") and d.get("start_longitude"):
                d["start_location"] = {
                    "latitude": d["start_latitude"],
                    "longitude": d["start_longitude"],
                    "timestamp": d.get("start_time")
                }
            if d.get("end_latitude") and d.get("end_longitude"):
                d["end_location"] = {
                    "latitude": d["end_latitude"],
                    "longitude": d["end_longitude"],
                    "timestamp": d.get("end_time")
                }
            return d
        return None

    def get_device_journeys(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves all journeys for a device in reverse chronological order."""
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    docs = db.collection("devices").document(device_id).collection("journeys")\
                        .order_by("created_at", direction="DESCENDING")\
                        .limit(limit)\
                        .stream(timeout=2.0)
                    results = []
                    for d in docs:
                        data = d.to_dict()
                        data["id"] = d.id
                        results.append(data)
                    if results:
                        return results
            except Exception as e:
                app_logger.error(f"Firestore get_device_journeys failed: {e}")

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM journeys WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
            (device_id, limit)
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["route_coordinates"] = json.loads(d.get("route_coordinates_json") or "[]")
            except Exception:
                d["route_coordinates"] = []
            if d.get("start_latitude") and d.get("start_longitude"):
                d["start_location"] = {
                    "latitude": d["start_latitude"],
                    "longitude": d["start_longitude"],
                    "timestamp": d.get("start_time")
                }
            if d.get("end_latitude") and d.get("end_longitude"):
                d["end_location"] = {
                    "latitude": d["end_latitude"],
                    "longitude": d["end_longitude"],
                    "timestamp": d.get("end_time")
                }
            results.append(d)
        return results

    def get_journey(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single journey by ID."""
        if is_firebase_active():
            try:
                db = get_firestore_client()
                if db:
                    doc = db.collection("journeys").document(journey_id).get(timeout=2.0)
                    if doc.exists:
                        data = doc.to_dict()
                        data["id"] = doc.id
                        return data
            except Exception as e:
                app_logger.error(f"Firestore get_journey failed: {e}")

        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM journeys WHERE journey_id = ?", (journey_id,)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            try:
                d["route_coordinates"] = json.loads(d.get("route_coordinates_json") or "[]")
            except Exception:
                d["route_coordinates"] = []
            if d.get("start_latitude") and d.get("start_longitude"):
                d["start_location"] = {
                    "latitude": d["start_latitude"],
                    "longitude": d["start_longitude"],
                    "timestamp": d.get("start_time")
                }
            if d.get("end_latitude") and d.get("end_longitude"):
                d["end_location"] = {
                    "latitude": d["end_latitude"],
                    "longitude": d["end_longitude"],
                    "timestamp": d.get("end_time")
                }
            return d
        return None


firestore_service = FirestoreService()
