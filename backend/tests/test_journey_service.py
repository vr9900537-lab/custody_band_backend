"""
Unit Tests for Travel Distance Tracking, Route Highlighting & Journey Lifecycle
Verifies:
1. Start Journey captures initial valid GPS fix as START marker
2. Live Route Tracking records valid GPS fixes and ignores duplicate/invalid points
3. Haversine distance calculation accumulates distance accurately along route
4. End Journey captures final GPS fix as END marker and computes duration
5. Separate journeys do not combine distance
6. API routes (/api/v1/journeys/start, /end, /active, /device) operate cleanly
"""

import unittest
from unittest.mock import patch, MagicMock
from app.services.journey_service import journey_service, format_duration
from app.services.gps_service import gps_service
from app.services.firestore_service import firestore_service
from app.journeys.journey_routes import (
    start_journey,
    end_journey,
    get_active_journey,
    StartJourneyRequest,
    EndJourneyRequest
)


class TestJourneyTracking(unittest.TestCase):
    def setUp(self):
        self.device_id = "863758061830955"

        # Mock Firestore client
        self.mock_db = MagicMock()
        self.saved_docs = {}

        def mock_set(data, merge=True):
            self.saved_docs[self.device_id] = dict(data)

        mock_doc = MagicMock()
        mock_doc.set.side_effect = mock_set
        mock_doc.get.return_value.exists = False
        mock_doc.get.return_value.to_dict.return_value = {}

        self.mock_db.collection.return_value.document.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
        self.mock_db.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []

        self.fs_patch1 = patch("app.services.firestore_service.get_firestore_client", return_value=self.mock_db)
        self.fs_patch2 = patch("app.core.firebase.get_firestore_client", return_value=self.mock_db)
        self.fs_patch1.start()
        self.fs_patch2.start()

        journey_service._active_journeys.clear()

        # Seed initial device fix in local storage
        firestore_service.save_device({
            "device_id": self.device_id,
            "last_latitude": 17.446317,
            "last_longitude": 78.368395,
            "gps_valid": True,
            "status": "ONLINE",
            "last_seen": "2026-11-06T10:00:00Z",
            "last_valid_gps_time": "2026-11-06T10:00:00Z"
        })

    def tearDown(self):
        journey_service.end_journey(self.device_id)
        journey_service._active_journeys.clear()
        self.fs_patch1.stop()
        self.fs_patch2.stop()

    def test_1_start_journey_captures_initial_valid_fix(self):
        """START JOURNEY captures first valid GPS fix and sets active status."""
        journey = journey_service.start_journey(self.device_id)
        self.assertIsNotNone(journey)
        self.assertEqual(journey["device_id"], self.device_id)
        self.assertEqual(journey["status"], "ACTIVE")
        self.assertIsNotNone(journey["start_location"])
        self.assertAlmostEqual(journey["start_location"]["latitude"], 17.446317, places=4)
        self.assertAlmostEqual(journey["start_location"]["longitude"], 78.368395, places=4)
        self.assertEqual(journey["total_distance_km"], 0.0)
        self.assertEqual(len(journey["route_coordinates"]), 1)

    def test_2_live_route_tracking_accumulates_distance_haversine(self):
        """LIVE ROUTE TRACKING calculates travelled distance using Haversine formula."""
        journey = journey_service.start_journey(self.device_id)

        # Move ~500 meters East: 17.446317, 78.368395 -> 17.446317, 78.373100
        point2_lat, point2_lon = 17.446317, 78.373100
        expected_dist_m = gps_service.calculate_distance_meters(17.446317, 78.368395, point2_lat, point2_lon)
        expected_km = expected_dist_m / 1000.0

        updated = journey_service.record_journey_point(
            self.device_id,
            latitude=point2_lat,
            longitude=point2_lon,
            timestamp="2026-11-06T10:05:00Z",
            speed_kmh=15.0
        )

        self.assertIsNotNone(updated)
        self.assertEqual(len(updated["route_coordinates"]), 2)
        self.assertAlmostEqual(updated["total_distance_km"], expected_km, places=2)
        self.assertGreater(updated["total_distance_km"], 0.4)

    def test_3_ignore_duplicate_and_invalid_points(self):
        """Does not record duplicate points or invalid (0.0, 0.0) coordinates."""
        journey = journey_service.start_journey(self.device_id)
        initial_points = len(journey["route_coordinates"])

        # Duplicate point (exact same coordinates)
        journey_service.record_journey_point(
            self.device_id,
            latitude=17.446317,
            longitude=78.368395,
            timestamp="2026-11-06T10:01:00Z"
        )
        active = journey_service.get_active_journey(self.device_id)
        self.assertEqual(len(active["route_coordinates"]), initial_points)

        # Noise under 2.5 meters
        journey_service.record_journey_point(
            self.device_id,
            latitude=17.446317001,
            longitude=78.368395001,
            timestamp="2026-11-06T10:02:00Z"
        )
        active = journey_service.get_active_journey(self.device_id)
        self.assertEqual(len(active["route_coordinates"]), initial_points)

        # Invalid (0, 0) coordinates
        journey_service.record_journey_point(
            self.device_id,
            latitude=0.0,
            longitude=0.0,
            timestamp="2026-11-06T10:03:00Z"
        )
        active = journey_service.get_active_journey(self.device_id)
        self.assertEqual(len(active["route_coordinates"]), initial_points)

    def test_4_end_journey_captures_end_marker_and_duration(self):
        """END JOURNEY captures final valid coordinates as END marker and computes duration."""
        journey_service.start_journey(self.device_id)

        # Move to destination
        journey_service.record_journey_point(
            self.device_id,
            latitude=17.449000,
            longitude=78.372000,
            timestamp="2026-11-06T10:15:00Z",
            speed_kmh=12.0
        )

        completed = journey_service.end_journey(self.device_id)
        self.assertIsNotNone(completed)
        self.assertEqual(completed["status"], "COMPLETED")
        self.assertIsNotNone(completed["end_time"])
        self.assertIsNotNone(completed["end_location"])
        self.assertAlmostEqual(completed["end_location"]["latitude"], 17.449000, places=4)
        self.assertAlmostEqual(completed["end_location"]["longitude"], 78.372000, places=4)
        self.assertGreaterEqual(completed["duration_seconds"], 0)
        self.assertIn(":", completed["duration_formatted"])

        # Active cache should be cleared
        self.assertIsNone(journey_service._active_journeys.get(self.device_id))

    def test_5_separate_journeys_do_not_combine_distance(self):
        """Verifies distance is isolated per journey and never carries over between journeys."""
        # Journey 1
        j1 = journey_service.start_journey(self.device_id)
        journey_service.record_journey_point(self.device_id, 17.448000, 78.370000, "2026-11-06T10:05:00Z")
        j1_completed = journey_service.end_journey(self.device_id)
        d1 = j1_completed["total_distance_km"]

        # Journey 2 starts from new location
        firestore_service.save_device({
            "device_id": self.device_id,
            "last_latitude": 17.450000,
            "last_longitude": 78.380000,
            "gps_valid": True,
            "last_valid_gps_time": "2026-11-06T11:00:00Z"
        })
        j2 = journey_service.start_journey(self.device_id)
        self.assertEqual(j2["total_distance_km"], 0.0)  # Starts at 0.0

        # Move small distance in journey 2
        journey_service.record_journey_point(self.device_id, 17.450500, 78.380500, "2026-11-06T11:05:00Z")
        j2_completed = journey_service.end_journey(self.device_id)
        d2 = j2_completed["total_distance_km"]

        self.assertNotEqual(d2, d1)
        self.assertLess(d2, 0.2)  # Should only measure journey 2 segment

    def test_6_api_endpoints_start_end_and_active(self):
        """Tests REST API endpoints for Journey tracking."""
        # Start via API route function
        resp = start_journey(StartJourneyRequest(device_id=self.device_id))
        self.assertTrue(resp["success"])
        self.assertEqual(resp["journey"]["status"], "ACTIVE")

        # Active query route function
        active_resp = get_active_journey(self.device_id)
        self.assertTrue(active_resp["active"])
        self.assertIsNotNone(active_resp["journey"])

        # End via API route function
        end_resp = end_journey(EndJourneyRequest(device_id=self.device_id))
        self.assertTrue(end_resp["success"])
        self.assertEqual(end_resp["journey"]["status"], "COMPLETED")

        # Active query now returns False
        active_resp_after = get_active_journey(self.device_id)
        self.assertFalse(active_resp_after["active"])


if __name__ == "__main__":
    unittest.main()
