#!/usr/bin/env python3
"""
Huaten C05 GPS Custody Watch - Live Traveling GPS & Directional Arrow Simulator
Simulates real-world movement along a travel path, dynamically calculating
heading/bearing angles (0-360°) and speeds so the map arrow physically moves
and rotates along the travel direction.
"""

import sys
import time
import socket
import json
import math
import urllib.request
from datetime import datetime, timezone

# Target configuration
HOST = "127.0.0.1"
API_PORT = 8000
TCP_PORT = 9001
DEVICE_IMEI = "863758061830955"
MAKER = "MNYD"
BATTERY_LEVEL = 90

# Realistic starting position (Hyderabad Hitec City / sample custody zone)
BASE_LAT = 17.446317
BASE_LON = 78.368395


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates forward compass heading (0-360 degrees) between two coordinates."""
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


def compass_direction_name(degrees: float) -> str:
    """Converts degrees into compass direction name."""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((degrees + 11.25) / 22.5) % 16
    return dirs[ix]


def send_http_gps(lat: float, lon: float, bearing: float, speed: float = 18.5, battery: int = BATTERY_LEVEL, steps: int = 2150, is_charging: bool = False):
    """Sends GPS fix via FastAPI HTTP ingest endpoint."""
    url = f"http://{HOST}:{API_PORT}/api/v1/gps/ingest"
    payload = {
        "device_id": DEVICE_IMEI,
        "maker": MAKER,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "lat": round(lat, 6),
        "lng": round(lon, 6),
        "lon": round(lon, 6),
        "heading": round(bearing, 1),
        "bearing": round(bearing, 1),
        "course": round(bearing, 1),
        "direction": round(bearing, 1),
        "angle": round(bearing, 1),
        "rotation": round(bearing, 1),
        "speed_kmh": round(speed, 1),
        "speed": round(speed, 1),
        "battery": battery,
        "battery_level": battery,
        "charge": battery,
        "is_charging": is_charging,
        "charging": is_charging,
        "charge_status": "charging" if is_charging else "discharging",
        "steps": steps,
        "gps_valid": True,
        "gps_fix": True,
        "gps_locked": True,
        "gps_status": "GPS Locked",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            dir_name = compass_direction_name(bearing)
            chg_str = " (⚡ Charging)" if is_charging else ""
            print(f"  [HTTP Ingest API] -> OK 200 | Lat: {lat:.6f}, Lon: {lon:.6f} | Heading: {bearing:5.1f}° ({dir_name}) | Speed: {speed:.1f} km/h | Batt: {battery}%{chg_str}")
            return True
    except Exception as e:
        print(f"  [HTTP Ingest Note] {e} (Backend HTTP on port {API_PORT} may not be running)")
        return False


def send_tcp_watch_packet(lat: float, lon: float, bearing: float, speed: float = 18.5, battery: int = BATTERY_LEVEL, steps: int = 2150, is_charging: bool = False):
    """
    Sends raw Huaten C05 protocol frame with course/heading:
    [MAKER*ID*LEN*UD,YYMMDD,HHMMSS,A,lat,N,lon,E,speed,course,alt,sats,gsm,batt,steps,term_status,...]
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M%S")
    status_hex = "00000010" if is_charging else "00000000"

    content = f"UD,{date_str},{time_str},A,{lat:.6f},N,{lon:.6f},E,{speed:.1f},{bearing:.1f},520.0,9,100,{battery},{steps},{status_hex},0,0,0,0,0"
    content_bytes = content.encode("latin-1")
    frame = b"[%s*%s*%04X*%s]" % (
        MAKER.encode("latin-1"),
        DEVICE_IMEI.encode("latin-1"),
        len(content_bytes),
        content_bytes
    )

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((HOST, TCP_PORT))
        sock.sendall(frame)
        try:
            reply = sock.recv(1024)
            print(f"  [TCP Port 9001  ] -> Frame delivered to watch receiver")
        except socket.timeout:
            print(f"  [TCP Port 9001  ] -> Frame delivered to watch receiver")
        sock.close()
        return True
    except Exception as e:
        # Expected if receiver isn't running or network test
        return False


def run_travel_simulation(count: int = 12, interval_sec: float = 2.0, loop_forever: bool = False):
    print("=" * 70)
    print(f"[*] Starting Real-time Travel & GPS Directional Arrow Movement...")
    print(f"    Target Device IMEI : {DEVICE_IMEI} (Custody Watch)")
    print(f"    Target HTTP API    : http://{HOST}:{API_PORT}/api/v1/gps/ingest")
    print(f"    Target Watch TCP   : {HOST}:{TCP_PORT}")
    print(f"    Current Battery    : {BATTERY_LEVEL}%")
    print("=" * 70)

    # 16-point circular/curved travel route demonstrating 360-degree arrow rotation
    radius = 0.0035  # ~380 meters patrol loop
    center_lat = BASE_LAT
    center_lon = BASE_LON

    step_idx = 0
    prev_lat = center_lat + radius
    prev_lon = center_lon

    total_steps = 999999 if loop_forever else count

    while step_idx < total_steps:
        step_idx += 1
        angle_rad = (step_idx * (2 * math.pi / 16)) % (2 * math.pi)

        # Move along curved perimeter
        cur_lat = center_lat + radius * math.cos(angle_rad)
        cur_lon = center_lon + radius * math.sin(angle_rad) * 1.05

        # Compute accurate forward heading
        bearing = calculate_bearing(prev_lat, prev_lon, cur_lat, cur_lon)
        speed = 14.0 + 8.0 * math.sin(angle_rad)  # Speed variation between 14 - 22 km/h
        steps = 1500 + step_idx * 18

        dir_label = compass_direction_name(bearing)
        arrow_icon = "⬆" if 337.5 <= bearing or bearing < 22.5 else (
            "↗" if bearing < 67.5 else (
                "➡" if bearing < 112.5 else (
                    "↘" if bearing < 157.5 else (
                        "⬇" if bearing < 202.5 else (
                            "↙" if bearing < 247.5 else (
                                "⬅" if bearing < 292.5 else "↖"
                            )
                        )
                    )
                )
            )
        )

        print(f"\n[Move Fix #{step_idx}] Time: {datetime.now().strftime('%H:%M:%S')}  {arrow_icon}  Travel Arrow Heading: {bearing:5.1f}° ({dir_label})")
        send_http_gps(cur_lat, cur_lon, bearing=bearing, speed=speed, steps=steps)
        send_tcp_watch_packet(cur_lat, cur_lon, bearing=bearing, speed=speed, steps=steps)

        prev_lat = cur_lat
        prev_lon = cur_lon

        if step_idx < total_steps:
            time.sleep(interval_sec)

    print("\n" + "=" * 70)
    print("[*] Travel simulation cycle finished!")
    print("    Check your frontend map dashboard: the travel arrow should have moved")
    print("    and rotated according to each directional waypoint!")
    print("=" * 70)


if __name__ == "__main__":
    is_loop = "--loop" in sys.argv or "--continuous" in sys.argv
    count = 12
    for arg in sys.argv[1:]:
        if arg.isdigit():
            count = int(arg)
            break

    # Battery and charging CLI arguments
    for i, a in enumerate(sys.argv):
        if a in ("--battery", "-b") and i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            BATTERY_LEVEL = int(sys.argv[i + 1])

    is_chg = "--charging" in sys.argv or "--charge" in sys.argv
    run_travel_simulation(count=count, interval_sec=2.0, loop_forever=is_loop)
