# =============================================================================
# ipc.py — Inter-Process Communication Abstraction Layer
# =============================================================================
# Provides a unified interface for sharing live DAQ data between the PyQt5
# app process and the Flask web server process.
#
# Platform selection (automatic via sys.platform):
#   Windows → JSON file (live_data.json) — SSD wear negligible
#   Linux   → Unix domain socket (/tmp/tcu.sock) — no SD card wear
#
# Usage (writer — daq_thread.py):
#   from ipc import IPCWriter
#   writer = IPCWriter()
#   writer.write(sample_dict)
#
# Usage (reader — web_server.py):
#   from ipc import IPCReader
#   reader = IPCReader()
#   data = reader.read()   # returns dict or None
# =============================================================================

import sys
import json
import os
import time

WINDOWS = sys.platform == 'win32'

# ── Platform-specific paths ───────────────────────────────────────────────────
JSON_PATH   = os.path.join(os.path.dirname(__file__), '.tcu_ipc.json')
SOCKET_PATH = '/tmp/tcu_ipc.sock'


# =============================================================================
# JSON file IPC (Windows)
# =============================================================================

class _JSONWriter:
    """
    Writes latest DAQ sample to a JSON file atomically.
    Atomic write (write to temp file then rename) prevents Flask from
    reading a half-written file.
    """

    def __init__(self):
        self._tmp = JSON_PATH + '.tmp'

    def write(self, data: dict):
        """Write data dict to JSON file atomically."""
        try:
            payload = json.dumps(data)
            with open(self._tmp, 'w') as f:
                f.write(payload)
            os.replace(self._tmp, JSON_PATH)   # atomic on both Windows and Linux
        except Exception as e:
            print(f"IPC write error: {e}")

    def close(self):
        """Clean up JSON file on shutdown."""
        for path in [JSON_PATH, self._tmp]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


class _JSONReader:
    """Reads latest DAQ sample from JSON file."""

    def read(self) -> dict | None:
        """Return latest data dict, or None if unavailable."""
        try:
            with open(JSON_PATH, 'r') as f:
                return json.loads(f.read())
        except (FileNotFoundError, json.JSONDecodeError):
            return None


# =============================================================================
# Unix domain socket IPC (Linux / RPi)
# =============================================================================

class _SocketWriter:
    """
    Serves latest DAQ sample over a Unix domain socket.
    Runs a background listener thread — clients connect, receive latest
    data as JSON, then disconnect.
    """

    def __init__(self):
        import socket
        import threading
        self._data    = None
        self._lock    = threading.Lock()
        self._running = True

        # Remove stale socket file if it exists
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(SOCKET_PATH)
        self._server.listen(5)
        self._server.settimeout(1.0)

        self._thread = threading.Thread(
            target=self._serve, daemon=True, name='IPCSocketServer')
        self._thread.start()

    def write(self, data: dict):
        """Update the latest data — thread safe."""
        with self._lock:
            self._data = data

    def _serve(self):
        """Accept connections and send latest data to each client."""
        import socket
        while self._running:
            try:
                conn, _ = self._server.accept()
                with self._lock:
                    payload = json.dumps(self._data) if self._data else '{}'
                try:
                    conn.sendall(payload.encode('utf-8'))
                finally:
                    conn.close()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"IPC socket serve error: {e}")

    def close(self):
        """Shut down socket server and clean up."""
        self._running = False
        self._server.close()
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass


class _SocketReader:
    """Reads latest DAQ sample from Unix domain socket."""

    def read(self) -> dict | None:
        """Connect to socket, read data and return as dict."""
        import socket
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(SOCKET_PATH)
                chunks = []
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b''.join(chunks).decode('utf-8')
                return json.loads(raw) if raw else None
        except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
            return None
        except Exception as e:
            print(f"IPC socket read error: {e}")
            return None


# =============================================================================
# Public interface — auto-selects platform implementation
# =============================================================================

def IPCWriter():
    """
    Factory — returns the correct writer for the current platform.

    Windows → _JSONWriter
    Linux   → _SocketWriter
    """
    if WINDOWS:
        return _JSONWriter()
    else:
        return _SocketWriter()


def IPCReader():
    """
    Factory — returns the correct reader for the current platform.

    Windows → _JSONReader
    Linux   → _SocketReader
    """
    if WINDOWS:
        return _JSONReader()
    else:
        return _SocketReader()
