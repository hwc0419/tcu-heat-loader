# =============================================================================
# pt100.py — PT100 Temperature Sensors (Wireless via ESP32 TCP)
# =============================================================================
# Manages two independent PT100 sensor nodes:
#   Node 1 — Inlet pipe  (cross-checks TCU RS232 inlet reading)
#   Node 2 — Outlet pipe (measures outlet fluid temperature)
#
# Both nodes run identical ESP32 MicroPython firmware.
# Protocol:
#   Request:  "GET_TEMP\n"
#   Response: "OUTLET_TEMP:23.45\n"
#
# If either node is disabled in config or unreachable,
# that node returns None gracefully — test continues without it.
# =============================================================================

import socket
from config import (
    PT100_INLET_ENABLED,  PT100_INLET_HOST,  PT100_INLET_PORT,  PT100_INLET_TIMEOUT,
    PT100_OUTLET_ENABLED, PT100_OUTLET_HOST, PT100_OUTLET_PORT, PT100_OUTLET_TIMEOUT
)


class _PT100Node:
    """
    Single ESP32 PT100 wireless sensor node.
    Internal class — use PT100Sensors instead.
    """

    def __init__(self, name, host, port, timeout):
        self.name      = name
        self.host      = host
        self.port      = port
        self.timeout   = timeout
        self.available = False
        self.sock      = None
        self._connect()

    def _connect(self):
        """Attempt TCP connection to ESP32 sensor node."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self.available = True
            print(f"PT100 [{self.name}] connected ({self.host}:{self.port})")
        except Exception as e:
            self.available = False
            print(f"PT100 [{self.name}] not reachable: {e}")
            print(f"  Check ESP32 is powered and on WiFi at {self.host}")

    def read(self):
        """
        Request temperature from ESP32 node.
        Returns float in °C rounded to 2dp, or None if unavailable.
        """
        if not self.available:
            return None
        try:
            self.sock.sendall(b'GET_TEMP\n')
            data = self.sock.recv(64).decode('ascii').strip()
            return round(float(data.split(':')[1]), 2)
        except Exception as e:
            print(f"PT100 [{self.name}] read error: {e} — attempting reconnect")
            self._connect()
            return None

    def close(self):
        """Close TCP socket."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


class PT100Sensors:
    """
    Manages both PT100 sensor nodes — inlet and outlet.

    Usage:
        sensors = PT100Sensors()
        inlet_pt100  = sensors.get_inlet_temp()   # independent inlet reading
        outlet_pt100 = sensors.get_outlet_temp()  # outlet reading
        sensors.close()
    """

    def __init__(self):
        self._inlet  = None
        self._outlet = None

        if PT100_INLET_ENABLED:
            self._inlet = _PT100Node(
                'INLET',
                PT100_INLET_HOST,
                PT100_INLET_PORT,
                PT100_INLET_TIMEOUT
            )
        else:
            print("PT100 inlet sensor disabled in config.py")

        if PT100_OUTLET_ENABLED:
            self._outlet = _PT100Node(
                'OUTLET',
                PT100_OUTLET_HOST,
                PT100_OUTLET_PORT,
                PT100_OUTLET_TIMEOUT
            )
        else:
            print("PT100 outlet sensor disabled in config.py")

    def get_inlet_temp(self):
        """
        Returns independent PT100 inlet temperature in °C, or None.
        Use to cross-check TCU RS232 inlet reading.
        """
        return self._inlet.read() if self._inlet else None

    def get_outlet_temp(self):
        """
        Returns PT100 outlet temperature in °C, or None.
        """
        return self._outlet.read() if self._outlet else None

    def close(self):
        """Close both TCP sockets."""
        if self._inlet:
            self._inlet.close()
        if self._outlet:
            self._outlet.close()
