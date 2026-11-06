"""
GPS Service
Coordinate parsing, Google Maps link generation, distance calculation & geofence checking.
"""

import math
from typing import Optional, Dict, Any, Tuple
from ..utils.datetime_utils import current_iso_timestamp
from ..utils.logger import gps_logger
from .firestore_service import firestore_service


class GPSService:
    @staticmethod
    def build_maps_url(lat: float, lon: float) -> str:
        """Generates standard Google Maps coordinate pin URL."""
        return f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"

    @staticmethod
    def calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates distance between two GPS coordinates using the Haversine formula."""
        R = 6371000  # Radius of Earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates forward azimuth / compass heading (0-360 degrees) from point 1 to point 2."""
        if lat1 == lat2 and lon1 == lon2:
            return 0.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)
        x = math.sin(delta_lambda) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
        initial_bearing = math.atan2(x, y)
        compass_bearing = (math.degrees(initial_bearing) + 360.0) % 360.0
        return round(compass_bearing, 1)

    @staticmethod
    def is_inside_geofence(
        lat: float, lon: float, center_lat: float, center_lon: float, radius_meters: float
    ) -> bool:
        """Returns True if point is within circle defined by center and radius."""
        dist = GPSService.calculate_distance_meters(lat, lon, center_lat, center_lon)
        return dist <= radius_meters

    def process_location_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Enriches and persists a location record with dynamic direction angle/bearing."""
        lat = record.get("latitude")
        lon = record.get("longitude")

        # Strict coordinate validation
        if lat is not None and lon is not None:
            try:
                f_lat = float(lat)
                f_lon = float(lon)
                is_coord_valid = (-90.0 <= f_lat <= 90.0) and (-180.0 <= f_lon <= 180.0) and not (f_lat == 0.0 and f_lon == 0.0)
            except (ValueError, TypeError):
                is_coord_valid = False
        else:
            is_coord_valid = False

        is_valid = bool(record.get("gps_valid", False)) and is_coord_valid
        record["gps_valid"] = is_valid
        record["gps_fix"] = is_valid
        record["gps_locked"] = is_valid
        record["gps_status"] = "GPS Locked" if is_valid else "No Fix"

        # 1. Resolve travel direction / arrow heading
        bearing = (
            record.get("heading")
            if record.get("heading") is not None
            else (record.get("bearing") if record.get("bearing") is not None else record.get("course"))
        )

        if bearing is None and is_valid and lat is not None and lon is not None:
            last_dev = firestore_service.get_device(record["device_id"])
            if last_dev and last_dev.get("last_latitude") and last_dev.get("last_longitude"):
                p_lat = last_dev["last_latitude"]
                p_lon = last_dev["last_longitude"]
                if p_lat != lat or p_lon != lon:
                    bearing = self.calculate_bearing(p_lat, p_lon, lat, lon)
                else:
                    bearing = last_dev.get("heading") or last_dev.get("bearing") or 0.0
            else:
                bearing = 0.0

        if bearing is None:
            bearing = 0.0

        bearing = float(bearing)
        record["heading"] = bearing
        record["bearing"] = bearing
        record["course"] = bearing
        record["direction"] = bearing
        record["angle"] = bearing
        record["rotation"] = bearing

        if is_valid and lat is not None and lon is not None:
            record["latitude"] = round(float(lat), 6)
            record["longitude"] = round(float(lon), 6)
            record["maps_url"] = self.build_maps_url(float(lat), float(lon))
            gps_logger.info(
                f"[GPS FIX] Device {record['device_id']} at ({float(lat):.6f}, {float(lon):.6f}) - Heading: {bearing}° - {record['maps_url']}"
            )
            # Live Journey Route Tracking
            try:
                from .journey_service import journey_service
                journey_service.record_journey_point(
                    device_id=record["device_id"],
                    latitude=float(lat),
                    longitude=float(lon),
                    timestamp=record.get("timestamp") or current_iso_timestamp(),
                    speed_kmh=float(record.get("speed_kmh") or record.get("speed") or 0.0)
                )
            except Exception as e:
                gps_logger.warning(f"Journey point record note: {e}")
        else:
            record["latitude"] = None
            record["longitude"] = None
            record["maps_url"] = None
            batt_info = f"Battery: {record.get('battery')}%" if record.get('battery') is not None else "Battery: N/A"
            gps_logger.info(
                f"[NO FIX] Device {record['device_id']} GPS invalid/indoor ({batt_info}, Steps: {record.get('steps')})"
            )

        firestore_service.save_telemetry(record)
        return record


gps_service = GPSService()

