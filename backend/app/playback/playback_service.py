"""
Historical Route Playback Service
Analyzes breadcrumb trails, calculates travel distance, and identifies dwell/stop locations.
"""

from typing import List, Dict, Any, Optional
from ..services.firestore_service import firestore_service
from ..services.gps_service import gps_service


class PlaybackService:
    def get_route_trail(
        self,
        device_id: str,
        limit: int = 200,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves chronological route coordinates and calculates travel distance.
        """
        raw_points = firestore_service.get_telemetry_history(device_id, limit=limit)

        # Filter valid GPS points with non-zero lat/lon
        valid_points = [
            p for p in raw_points
            if p.get("gps_valid") and p.get("latitude") and p.get("longitude")
        ]

        # Reverse to chronological order (oldest to newest)
        valid_points.reverse()

        total_distance_meters = 0.0
        dwell_stops = []

        for i in range(len(valid_points) - 1):
            p1 = valid_points[i]
            p2 = valid_points[i + 1]
            dist = gps_service.calculate_distance_meters(
                p1["latitude"], p1["longitude"],
                p2["latitude"], p2["longitude"]
            )
            total_distance_meters += dist

            # Dwell point detection (moved less than 20 meters between consecutive records)
            if dist < 20:
                dwell_stops.append({
                    "latitude": p1["latitude"],
                    "longitude": p1["longitude"],
                    "timestamp": p1.get("timestamp"),
                    "maps_url": p1.get("maps_url")
                })

        return {
            "device_id": device_id,
            "total_points": len(valid_points),
            "total_distance_km": round(total_distance_meters / 1000.0, 2),
            "dwell_stops_count": len(dwell_stops),
            "route": valid_points,
            "dwell_stops": dwell_stops[:10]  # Top 10 dwell locations
        }


playback_service = PlaybackService()

