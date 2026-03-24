# =============================================================================
# esp32/main.py — ESP32 MicroPython Wireless PT100 Sensor Node
# =============================================================================
# Runs on ESP32-WROOM-32 flashed with MicroPython.
# Reads PT100 outlet temperature via MAX31865 (SPI).
# Serves temperature data to Toughbook via WiFi TCP socket.
#
# Hardware connections (ESP32 → MAX31865):
#   3V3  → VIN
#   GND  → GND
#   GPIO18 (SCK)  → SCK
#   GPIO19 (MISO) → SDO
#   GPIO23 (MOSI) → SDI
#   GPIO5  (CS)   → CS
#
# PT100 → MAX31865 screw terminals:
#   Wire 1 → F+
#   Wire 2 → F-
#   Wire 3 → RTD-
#   Jumper: bridge RTD+ to F+ for 3-wire configuration
#
# Protocol:
#   Client sends:   "GET_TEMP\n"
#   Server replies: "OUTLET_TEMP:23.45\n"
#   On error:       "ERROR:message\n"
#
# Upload this file to ESP32 root as main.py using Thonny or ampy.
# =============================================================================

import network
import socket
import time
from machine import SPI, Pin

# =============================================================================
# Configuration — update these before flashing
# =============================================================================
WIFI_SSID     = 'your_workshop_wifi'    # workshop WiFi network name
WIFI_PASSWORD = 'your_wifi_password'    # workshop WiFi password
TCP_PORT      = 5000                    # must match PT100_PORT in config.py
MAX_CLIENTS   = 1                       # one Toughbook at a time

# SPI pins (VSPI bus on ESP32)
PIN_SCK  = 18
PIN_MISO = 19
PIN_MOSI = 23
PIN_CS   = 5

# PT100 RTD nominal resistance at 0°C
RTD_NOMINAL  = 100.0   # PT100 = 100Ω at 0°C
RTD_WIRES    = 3       # 3-wire configuration
REF_RESISTOR = 430.0   # reference resistor on MAX31865 board (check datasheet)

# =============================================================================
# MAX31865 register definitions
# =============================================================================
MAX31865_CONFIG_REG        = 0x00
MAX31865_CONFIG_BIAS       = 0x80
MAX31865_CONFIG_MODEAUTO   = 0x40
MAX31865_CONFIG_1SHOT      = 0x20
MAX31865_CONFIG_3WIRE      = 0x10
MAX31865_CONFIG_CLRFAULT   = 0x02
MAX31865_RTDMSB_REG        = 0x01
MAX31865_FAULTSTAT_REG     = 0x07

# =============================================================================
# MAX31865 driver
# =============================================================================

class MAX31865:
    """Minimal MicroPython driver for MAX31865 RTD amplifier."""

    def __init__(self, spi, cs_pin):
        self.spi = spi
        self.cs  = cs_pin
        self.cs.value(1)
        self._configure()

    def _write_register(self, reg, value):
        self.cs.value(0)
        self.spi.write(bytes([reg | 0x80, value]))
        self.cs.value(1)

    def _read_register(self, reg, length=1):
        self.cs.value(0)
        self.spi.write(bytes([reg & 0x7F]))
        data = self.spi.read(length)
        self.cs.value(1)
        return data

    def _configure(self):
        """Configure MAX31865 for 3-wire PT100, auto conversion mode."""
        config = (MAX31865_CONFIG_BIAS |
                  MAX31865_CONFIG_MODEAUTO |
                  MAX31865_CONFIG_3WIRE |
                  MAX31865_CONFIG_CLRFAULT)
        self._write_register(MAX31865_CONFIG_REG, config)
        time.sleep_ms(100)

    def read_rtd(self):
        """Read raw RTD resistance value from MAX31865."""
        data = self._read_register(MAX31865_RTDMSB_REG, 2)
        rtd_raw = ((data[0] << 8) | data[1]) >> 1
        return rtd_raw

    def read_fault(self):
        """Read fault status register."""
        data = self._read_register(MAX31865_FAULTSTAT_REG, 1)
        return data[0]

    @property
    def temperature(self):
        """
        Calculate temperature from RTD resistance using Callendar-Van Dusen
        approximation (accurate to ±0.03°C for -20 to 100°C range).
        Returns temperature in °C as float.
        """
        rtd_raw  = self.read_rtd()
        rtd_res  = (rtd_raw / 32768.0) * REF_RESISTOR

        # Callendar-Van Dusen coefficients for PT100
        A = 3.9083e-3
        B = -5.775e-7

        # Quadratic approximation: R(T) = R0 * (1 + A*T + B*T^2)
        # Solving for T: T = (-A + sqrt(A^2 - 4*B*(1 - R/R0))) / (2*B)
        discriminant = (A ** 2) - 4 * B * (1 - rtd_res / RTD_NOMINAL)
        temp = (-A + discriminant ** 0.5) / (2 * B)
        return round(temp, 2)


# =============================================================================
# WiFi connection
# =============================================================================

def connect_wifi():
    """Connect to workshop WiFi. Blocks until connected."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print(f"WiFi already connected: {wlan.ifconfig()}")
        return wlan

    print(f"Connecting to WiFi: {WIFI_SSID}")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    timeout = 30
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
        print(".", end="")

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nWiFi connected — IP: {ip}")
        print(f"Update PT100_HOST = '{ip}' in Toughbook config.py")
        return wlan
    else:
        print("\nWiFi connection failed — check SSID and password")
        return None


# =============================================================================
# TCP server
# =============================================================================

def run_server(rtd):
    """Run TCP server — accept connections and respond to GET_TEMP requests."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', TCP_PORT))
    server.listen(MAX_CLIENTS)
    print(f"TCP server listening on port {TCP_PORT}")

    while True:
        try:
            conn, addr = server.accept()
            print(f"Client connected: {addr}")

            try:
                request = conn.recv(64).decode('ascii').strip()

                if request == 'GET_TEMP':
                    temp     = rtd.temperature
                    fault    = rtd.read_fault()

                    if fault != 0:
                        response = f"ERROR:fault_register={fault:#04x}\n"
                        print(f"MAX31865 fault: {fault:#04x}")
                    else:
                        response = f"OUTLET_TEMP:{temp:.2f}\n"
                        print(f"Sent: {response.strip()}")

                    conn.sendall(response.encode('ascii'))
                else:
                    conn.sendall(b"ERROR:unknown_command\n")

            except Exception as e:
                print(f"Request error: {e}")
                try:
                    conn.sendall(f"ERROR:{e}\n".encode('ascii'))
                except Exception:
                    pass
            finally:
                conn.close()

        except Exception as e:
            print(f"Server error: {e}")
            time.sleep(1)


# =============================================================================
# Entry point
# =============================================================================

def main():
    # Initialise SPI bus and MAX31865
    spi = SPI(
        1,
        baudrate  = 1_000_000,
        polarity  = 0,
        phase     = 1,
        sck       = Pin(PIN_SCK),
        mosi      = Pin(PIN_MOSI),
        miso      = Pin(PIN_MISO)
    )
    cs  = Pin(PIN_CS, Pin.OUT)
    rtd = MAX31865(spi, cs)
    print("MAX31865 initialised")

    # Test read on startup
    try:
        temp = rtd.temperature
        print(f"Initial PT100 reading: {temp:.2f}°C")
    except Exception as e:
        print(f"PT100 read failed on startup: {e}")

    # Connect to WiFi
    wlan = connect_wifi()
    if wlan is None:
        print("Cannot start server without WiFi")
        return

    # Start TCP server
    run_server(rtd)


main()
