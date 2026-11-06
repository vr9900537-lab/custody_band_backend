"""
Multi-Threaded TCP & UDP Watch Receiver
Binds to 0.0.0.0:9001 to accept traffic arriving from 103.44.0.5:9001.
"""

import socket
import threading
import time
from typing import Dict, Any, Optional
from ..config import settings
from ..utils.logger import tcp_logger
from .packet_validator import extract_frames
from .packet_parser import parse_packet, build_frame

active_connections: Dict[str, socket.socket] = {}
conn_lock = threading.Lock()
_receiver_started = False


def register_client(dev_id: str, conn: socket.socket):
    with conn_lock:
        active_connections[dev_id] = conn


def unregister_client(dev_id: str):
    with conn_lock:
        active_connections.pop(dev_id, None)


def get_active_clients_count() -> int:
    with conn_lock:
        return len(active_connections)


def send_command_to_device(device_id: str, command: str, maker: str = "MNYD") -> bool:
    """Sends a protocol command frame (e.g. CR for live GPS) to a connected watch."""
    with conn_lock:
        conn = active_connections.get(device_id)

    if not conn:
        tcp_logger.warning(f"Cannot send command '{command}': Device {device_id} is not currently connected")
        return False

    frame = build_frame(maker, device_id, command)
    try:
        conn.sendall(frame)
        tcp_logger.info(f"[{maker}*{device_id}] Sent Command <- {command}")
        return True
    except Exception as e:
        tcp_logger.error(f"Failed to send command to {device_id}: {e}")
        return False


def handle_tcp_client(conn: socket.socket, addr):
    client_str = f"{addr[0]}:{addr[1]}"
    tcp_logger.info(f"TCP connection established from {client_str}")
    assigned_device_id = None
    buffer = b""

    try:
        conn.settimeout(300)  # 5 minutes idle timeout
        while True:
            data = conn.recv(4096)
            if not data:
                break

            buffer += data
            frames, buffer = extract_frames(buffer)

            for maker, dev_id, content in frames:
                assigned_device_id = dev_id
                register_client(dev_id, conn)

                cmd_type, reply_bytes = parse_packet(maker, dev_id, content)

                # Send mandatory protocol reply
                if reply_bytes:
                    try:
                        conn.sendall(reply_bytes)
                        tcp_logger.info(f"[{maker}*{dev_id}] Sent Reply <- {reply_bytes.decode('latin-1', errors='ignore')}")
                    except Exception as e:
                        tcp_logger.error(f"Send reply error: {e}")

                # Auto-poll GPS on connection PING if enabled
                if cmd_type == "PING" and settings.AUTO_POLL_GPS_ON_PING:
                    def poll_gps_delayed(m=maker, d=dev_id, c=conn):
                        time.sleep(0.5)
                        try:
                            cr_frame = build_frame(m, d, "CR")
                            c.sendall(cr_frame)
                            tcp_logger.info(f"[{m}*{d}] Sent <- CR (Auto-polling live GPS)")
                        except Exception:
                            pass
                    threading.Thread(target=poll_gps_delayed, daemon=True).start()

    except socket.timeout:
        tcp_logger.info(f"TCP connection {client_str} timed out (device sleeping)")
    except Exception as e:
        tcp_logger.error(f"TCP connection {client_str} error: {e}")
    finally:
        if assigned_device_id:
            unregister_client(assigned_device_id)
        conn.close()
        tcp_logger.info(f"TCP connection {client_str} closed")


_tcp_server_sock: Optional[socket.socket] = None
_udp_server_sock: Optional[socket.socket] = None


def run_tcp_server():
    global _tcp_server_sock
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _tcp_server_sock = server
    try:
        server.bind((settings.TCP_HOST, settings.TCP_PORT))
        server.listen(10)
        tcp_logger.info(f"TCP Watch Receiver listening on {settings.TCP_HOST}:{settings.TCP_PORT} (Public IP: {settings.PUBLIC_SERVER_IP})")
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()
            except OSError:
                break
    except Exception as e:
        tcp_logger.critical(f"TCP Server encountered fatal error: {e}")


def run_udp_server():
    global _udp_server_sock
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _udp_server_sock = udp_sock
    try:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind((settings.TCP_HOST, settings.TCP_PORT))
        tcp_logger.info(f"UDP Watch Receiver listening on {settings.TCP_HOST}:{settings.TCP_PORT}")
        while True:
            try:
                data, addr = udp_sock.recvfrom(4096)
                frames, _ = extract_frames(data)
                for maker, dev_id, content in frames:
                    cmd_type, reply_bytes = parse_packet(maker, dev_id, content)
                    if reply_bytes:
                        udp_sock.sendto(reply_bytes, addr)
            except OSError:
                break
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or "10048" in str(e):
            tcp_logger.info(f"UDP port {settings.TCP_PORT} is shared or reserved. Running on primary TCP listener.")
        else:
            tcp_logger.info(f"UDP Server notice: {e}")
    except Exception as e:
        tcp_logger.info(f"UDP Server notice: {e}")


def stop_receiver():
    """Closes server sockets cleanly on application reload or shutdown."""
    global _tcp_server_sock, _udp_server_sock, _receiver_started
    _receiver_started = False
    if _tcp_server_sock:
        try:
            _tcp_server_sock.close()
        except Exception:
            pass
        _tcp_server_sock = None
    if _udp_server_sock:
        try:
            _udp_server_sock.close()
        except Exception:
            pass
        _udp_server_sock = None


def start_receiver_background():
    """Starts TCP and UDP receiver threads in background."""
    global _receiver_started
    if _receiver_started:
        return
    _receiver_started = True

    t_tcp = threading.Thread(target=run_tcp_server, daemon=True, name="TCPReceiverThread")
    t_tcp.start()

    t_udp = threading.Thread(target=run_udp_server, daemon=True, name="UDPReceiverThread")
    t_udp.start()

