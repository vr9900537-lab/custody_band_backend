"""
Packet Parser for Huaten C05 GPS Custody Watch
Decodes command payloads: PING, KA, UD (GPS), CRUD (Polled GPS), heart, and AL (Alarms).
"""

from typing import Optional, Dict, Any, Tuple
from ..utils.datetime_utils import current_iso_timestamp
from ..utils.logger import tcp_logger, gps_logger
from ..services.gps_service import gps_service
from ..services.device_service import device_service
from ..services.alert_service import alert_service

REPLIES = {
    "PING": "PING,1",
    "KA": "KA",
    "LK": "LK",
    "heart": "heart",
    "AL": "AL",
}


def build_frame(maker: str, dev_id: str, content: str) -> bytes:
    """Builds a compliant [MAKER*ID*HEX_LEN*CONTENT] frame."""
    body = content.encode("latin-1")
    return b"[%s*%s*%04X*%s]" % (maker.encode("latin-1"), dev_id.encode("latin-1"), len(body), body)


def parse_ud(content: bytes, device_id: str, maker: str) -> Optional[Dict[str, Any]]:
    """
    Parses Huaten UD / CRUD / AL packets:
    fields[0] : Command (UD / CRUD / AL)
    fields[1] : Date YYMMDD (e.g. 261102)
    fields[2] : UTC Time HHMMSS (e.g. 092137)
    fields[3] : Status (A = Valid GPS fix, V = Void / Indoor LBS)
    fields[4] : Latitude (e.g. 17.446317)
    fields[5] : Lat Hem (N/S)
    fields[6] : Longitude (e.g. 78.368395)
    fields[7] : Lon Hem (E/W)
    fields[8] : Speed km/h
    fields[9] : Course (Heading)
    fields[10]: Altitude
    fields[11]: Satellites
    fields[12]: GSM Signal
    fields[13]: Battery %
    fields[14]: Step Count
    fields[15]: Terminal Status (Hex)
    """
    try:
        msg = content.decode("latin-1", errors="ignore")
        fields = msg.split(",")
        if len(fields) < 15:
            return None

        cmd = fields[0].strip()
        date_str = fields[1].strip()
        time_str = fields[2].strip()
        status = fields[3].strip().upper()

        # Coordinate parsing and strict validation
        try:
            lat = float(fields[4].strip()) if fields[4].strip() else 0.0
        except (ValueError, TypeError):
            lat = 0.0
        if len(fields) > 5 and fields[5].strip().upper() == "S":
            lat = -abs(lat)

        try:
            lon = float(fields[6].strip()) if fields[6].strip() else 0.0
        except (ValueError, TypeError):
            lon = 0.0
        if len(fields) > 7 and fields[7].strip().upper() == "W":
            lon = -abs(lon)

        # Coordinate boundary checks (-90 <= lat <= 90, -180 <= lon <= 180, not 0,0)
        is_valid_coords = (-90.0 <= lat <= 90.0) and (-180.0 <= lon <= 180.0) and not (lat == 0.0 and lon == 0.0)
        is_valid_gps = (status == "A") and is_valid_coords

        try:
            speed = float(fields[8].strip()) if len(fields) > 8 and fields[8].strip() else 0.0
        except (ValueError, TypeError):
            speed = 0.0

        try:
            course = float(fields[9].strip()) if len(fields) > 9 and fields[9].strip() else 0.0
        except (ValueError, TypeError):
            course = 0.0

        satellites = int(fields[11].strip()) if len(fields) > 11 and fields[11].strip().isdigit() else 0
        gsm_signal = int(fields[12].strip()) if len(fields) > 12 and fields[12].strip().isdigit() else 0

        # Actual device battery - NEVER default to 90 or 100
        battery = int(fields[13].strip()) if len(fields) > 13 and fields[13].strip().isdigit() else None
        steps = int(fields[14].strip()) if len(fields) > 14 and fields[14].strip().isdigit() else None

        # Field 15: Terminal status (Hex 8 digits)
        is_charging = False
        if len(fields) > 15:
            try:
                term_hex = fields[15].strip()
                status_int = int(term_hex, 16) if term_hex else 0
                is_charging = bool(status_int & 0x10 or status_int & 0x08)
            except Exception:
                pass

        gps_status = "GPS Locked" if is_valid_gps else "No Fix"

        record: Dict[str, Any] = {
            "device_id": device_id,
            "maker": maker,
            "command": cmd,
            "timestamp": current_iso_timestamp(),
            "watch_date": date_str,
            "watch_time_utc": time_str,
            "gps_valid": is_valid_gps,
            "gps_fix": is_valid_gps,
            "gps_locked": is_valid_gps,
            "gps_status": gps_status,
            "latitude": round(lat, 6) if is_valid_gps else None,
            "longitude": round(lon, 6) if is_valid_gps else None,
            "speed_kmh": speed,
            "speed": speed,
            "heading": course,
            "bearing": course,
            "course": course,
            "direction": course,
            "direction_deg": course,
            "satellites": satellites,
            "gsm_signal": gsm_signal,
            "is_charging": is_charging,
            "charging": is_charging,
            "charge_status": "charging" if is_charging else "discharging",
        }

        if battery is not None:
            record["battery"] = battery
            record["battery_level"] = battery
            record["battery_percent"] = battery
            record["battery_status"] = "normal" if battery > 20 else "low"

        if steps is not None:
            record["steps"] = steps

        # Check nearby Wi-Fi APs
        if len(fields) > 24 and fields[24].strip().isdigit():
            record["nearby_wifi_count"] = int(fields[24].strip())

        # Process through GPS service and Device service
        gps_service.process_location_record(record)
        device_service.update_position(
            device_id=device_id,
            lat=round(lat, 6) if is_valid_gps else None,
            lon=round(lon, 6) if is_valid_gps else None,
            battery=battery,
            steps=steps,
            speed=speed,
            bearing=course,
            is_charging=is_charging,
            gps_valid=is_valid_gps,
            satellites=satellites,
            gsm_signal=gsm_signal
        )

        if battery is not None:
            alert_service.check_battery_alert(device_id, battery)

        # Check alarm conditions
        if cmd == "AL":
            alert_service.trigger_alert(
                device_id=device_id,
                alert_type="SOS",
                message="SOS Alarm triggered by wearer",
                latitude=record.get("latitude"),
                longitude=record.get("longitude")
            )

        return record

    except Exception as e:
        tcp_logger.error(f"Error parsing UD packet: {e}")
        return None


def parse_packet(maker: str, dev_id: str, content: bytes) -> Tuple[Optional[str], Optional[bytes]]:
    """
    Decodes packet content, dispatches business logic, and returns (cmd_type, reply_frame_bytes).
    """
    msg = content.decode("latin-1", errors="ignore")
    cmd = msg.split(",")[0]
    reply_bytes = None

    tcp_logger.info(f"[{maker}*{dev_id}] Recv -> {msg}")

    # Build acknowledgment reply if required by protocol
    if cmd in REPLIES:
        reply_body = REPLIES[cmd]
        reply_bytes = build_frame(maker, dev_id, reply_body)

    # 1. Location / Telemetry
    if cmd in ("UD", "CRUD", "AL"):
        parse_ud(content, dev_id, maker)

    # 2. Keepalive (KA)
    elif cmd == "KA":
        parts = msg.split(",")
        bat = None
        steps = None
        is_charging = False
        # Standard Huaten KA: KA,steps,rolls,battery[,charging]
        if len(parts) >= 4 and parts[3].strip().isdigit():
            bat = int(parts[3].strip())
            if len(parts) > 1 and parts[1].strip().isdigit():
                steps = int(parts[1].strip())
            if len(parts) > 4 and parts[4].strip() in ("1", "true"):
                is_charging = True
        elif len(parts) >= 5 and parts[4].strip().isdigit():
            bat = int(parts[4].strip())
            if len(parts) > 2 and parts[2].strip().isdigit():
                steps = int(parts[2].strip())
            if len(parts) > 5 and parts[5].strip() in ("1", "true"):
                is_charging = True
        else:
            for p in parts[1:]:
                p_c = p.strip()
                if p_c.isdigit():
                    v = int(p_c)
                    if 1 <= v <= 100 and bat is None:
                        bat = v
                    elif v > 100 and steps is None:
                        steps = v

        device_service.update_heartbeat(dev_id, bat, steps, is_charging=is_charging)
        if bat is not None:
            alert_service.check_battery_alert(dev_id, bat)

    # 3. Heart Rate
    elif cmd == "heart":
        parts = msg.split(",")
        bpm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        device_service.update_heart_rate(dev_id, bpm)

    # 4. Link & Status Heartbeat (LK)
    elif cmd == "LK":
        parts = msg.split(",")
        bat = None
        steps = None
        is_charging = False
        # Huaten LK frame formats: LK,steps,rolls,battery or LK,battery
        if len(parts) >= 4 and parts[3].strip().isdigit():
            bat = int(parts[3].strip())
            if len(parts) > 1 and parts[1].strip().isdigit():
                steps = int(parts[1].strip())
            if len(parts) > 4 and parts[4].strip() in ("1", "true"):
                is_charging = True
        else:
            for p in parts[1:]:
                p_clean = p.strip()
                if p_clean.isdigit():
                    val = int(p_clean)
                    if 1 <= val <= 100 and bat is None:
                        bat = val
                    elif val > 100 and steps is None:
                        steps = val
            if len(parts) > 4 and parts[4].strip() in ("1", "true"):
                is_charging = True

        device_service.update_heartbeat(dev_id, bat, steps, is_charging=is_charging)
        if bat is not None:
            alert_service.check_battery_alert(dev_id, bat)

    return cmd, reply_bytes

