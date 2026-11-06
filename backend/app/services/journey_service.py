"""
Journey Tracking Service
Manages real-time custody band travel routes, calculates travelled distance
using the Haversine formula, and synchronizes journey lifecycle to Firestore & SQLite.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from ..utils.datetime_utils import current_iso_timestamp
from ..utils.logger import app_logger, gps_logger
from .firestore_service import firestore_service
from .gps_service import gps_service


def format_duration(seconds: float) -> str:
    """Formats duration in seconds to HH:MM:SS."""
    s = int(max(0, seconds))
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class JourneyService:
    def __init__(self):
        # In-memory fast cache for active journeys: device_id -> journey_dict
        self._active_journeys: Dict[str, Dict[str, Any]] = {}

    def get_active_journey(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Returns the current active journey for a device, checking memory and persistence."""
        if device_id in self._active_journeys:
            return self._active_journeys[device_id]

        persisted = firestore_service.get_active_journey(device_id)
        if persisted:
            self._active_journeys[device_id] = persisted
            return persisted

        return None

    def start_journey(self, device_id: str) -> Dict[str, Any]:
        """
        Starts a new journey for the custody device.
        Captures initial valid coordinates if available, otherwise initializes
        to capture the first valid incoming GPS fix.
        """
        # If an active journey already exists, return it
        existing = self.get_active_journey(device_id)
        if existing and existing.get("status") == "ACTIVE":
            app_logger.info(f"[JOURNEY] Device {device_id} already has active journey {existing.get('journey_id')}")
            return existing

        now_iso = current_iso_timestamp()
        journey_id = f"journey_{device_id}_{int(datetime.now(timezone.utc).timestamp())}"

        # Check latest device location
        dev = firestore_service.get_device(device_id) or {}
        lat = dev.get("last_latitude")
        lon = dev.get("last_longitude")
        gps_valid = bool(dev.get("gps_valid", False)) and (lat is not None and lon is not None)

        start_location = None
        route_coordinates: List[Dict[str, Any]] = []

        if gps_valid and lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
            start_location = {
                "latitude": round(float(lat), 6),
                "longitude": round(float(lon), 6),
                "timestamp": dev.get("last_valid_gps_time") or now_iso,
                "speed_kmh": float(dev.get("speed_kmh") or dev.get("speed") or 0.0)
            }
            route_coordinates.append(start_location)

        journey: Dict[str, Any] = {
            "journey_id": journey_id,
            "id": journey_id,
            "device_id": device_id,
            "status": "ACTIVE",
            "start_time": now_iso,
            "end_time": None,
            "start_location": start_location,
            "end_location": None,
            "route_coordinates": route_coordinates,
            "total_distance_km": 0.0,
            "duration_seconds": 0,
            "duration_formatted": "00:00:00",
            "points_count": len(route_coordinates),
            "created_at": now_iso,
            "updated_at": now_iso
        }

        self._active_journeys[device_id] = journey
        firestore_service.save_journey(journey)
        app_logger.info(f"[JOURNEY START] Device {device_id} started journey {journey_id} (Initial fix: {bool(start_location)})")
        return journey

    def record_journey_point(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        timestamp: str,
        speed_kmh: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Records a valid incoming GPS coordinate during an active journey.
        Validates coordinates, ignores duplicates, and calculates Haversine distance.
        """
        journey = self.get_active_journey(device_id)
        if not journey or journey.get("status") != "ACTIVE":
            return None

        # Validate coordinate bounds
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0 and (latitude != 0.0 or longitude != 0.0)):
            return None

        new_point = {
            "latitude": round(float(latitude), 6),
            "longitude": round(float(longitude), 6),
            "timestamp": timestamp,
            "speed_kmh": round(float(speed_kmh), 1)
        }

        route = journey.get("route_coordinates", [])

        # If start_location was not captured at start click, lock it in now
        if not journey.get("start_location"):
            journey["start_location"] = new_point
            route = [new_point]
            journey["route_coordinates"] = route
            journey["points_count"] = 1
            journey["updated_at"] = timestamp
            firestore_service.save_journey(journey)
            app_logger.info(f"[JOURNEY] Device {device_id} locked initial START fix: ({latitude}, {longitude})")
            return journey

        # Duplicate check: compare against last recorded point
        if route:
            prev_point = route[-1]
            prev_lat = prev_point["latitude"]
            prev_lon = prev_point["longitude"]

            # Exact duplicate check
            if prev_lat == new_point["latitude"] and prev_lon == new_point["longitude"]:
                return journey

            # Haversine distance from previous point in meters
            dist_meters = gps_service.calculate_distance_meters(
                prev_lat, prev_lon,
                new_point["latitude"], new_point["longitude"]
            )

            # Ignore noise under 2.5 meters
            if dist_meters < 2.5:
                return journey

            incremental_km = dist_meters / 1000.0
            journey["total_distance_km"] = round(float(journey.get("total_distance_km", 0.0)) + incremental_km, 3)

        route.append(new_point)
        journey["route_coordinates"] = route
        journey["points_count"] = len(route)
        journey["updated_at"] = timestamp

        # Compute current elapsed duration
        try:
            st = datetime.fromisoformat(journey["start_time"].replace("Z", "+00:00"))
            ct = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            dur = max(0, (ct - st).total_seconds())
            journey["duration_seconds"] = int(dur)
            journey["duration_formatted"] = format_duration(dur)
        except Exception:
            pass

        firestore_service.save_journey(journey)
        return journey

    def end_journey(self, device_id: str, journey_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Ends an active journey for the custody device.
        Captures final valid GPS coordinates, sets end timestamp,
        computes final duration and distance.
        """
        journey = self.get_active_journey(device_id)
        if not journey:
            # Check if specific journey_id was requested
            if journey_id:
                journey = firestore_service.get_journey(journey_id)
            if not journey or journey.get("status") != "ACTIVE":
                app_logger.warning(f"[JOURNEY END] No active journey found for device {device_id}")
                return None

        now_iso = current_iso_timestamp()
        route = journey.get("route_coordinates", [])

        # End location is the last valid point in the route or device's current valid location
        end_location = None
        if route:
            end_location = route[-1]
        else:
            dev = firestore_service.get_device(device_id) or {}
            lat = dev.get("last_latitude")
            lon = dev.get("last_longitude")
            if lat is not None and lon is not None and (lat != 0.0 or lon != 0.0):
                end_location = {
                    "latitude": round(float(lat), 6),
                    "longitude": round(float(lon), 6),
                    "timestamp": dev.get("last_valid_gps_time") or now_iso,
                    "speed_kmh": float(dev.get("speed_kmh") or 0.0)
                }

        journey["status"] = "COMPLETED"
        journey["end_time"] = now_iso
        journey["end_location"] = end_location
        journey["updated_at"] = now_iso

        # Calculate final duration
        try:
            st = datetime.fromisoformat(journey["start_time"].replace("Z", "+00:00"))
            et = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
            dur = max(0, (et - st).total_seconds())
            journey["duration_seconds"] = int(dur)
            journey["duration_formatted"] = format_duration(dur)
        except Exception:
            journey["duration_seconds"] = 0
            journey["duration_formatted"] = "00:00:00"

        # Remove from active cache
        self._active_journeys.pop(device_id, None)

        firestore_service.save_journey(journey)
        app_logger.info(
            f"[JOURNEY END] Device {device_id} completed journey {journey['journey_id']}: "
            f"Distance: {journey['total_distance_km']} km, Duration: {journey['duration_formatted']}, Points: {len(route)}"
        )
        return journey

    def get_device_journeys(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns completed and active journey history for a device."""
        return firestore_service.get_device_journeys(device_id, limit=limit)

    def get_journey(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """Returns full journey details by ID."""
        return firestore_service.get_journey(journey_id)


journey_service = JourneyService()

