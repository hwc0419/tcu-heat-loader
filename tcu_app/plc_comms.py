# =============================================================================
# plc_comms.py — FP0-C14CRS MEWTOCOL Communication
# =============================================================================
import serial
import threading
import time
from config import (
    PLC_BAUD, PLC_BYTESIZE, PLC_PARITY, PLC_STOPBITS, PLC_TIMEOUT,
    PLC_UNIT, PLC_DT_SETPOINT, PLC_K_MIN, PLC_K_MAX,
    PLC_MAX_RETRIES, PLC_RETRY_DELAY,
)
from settings_manager import settings


def _bcc(frame: str) -> str:
    """
    MEWTOCOL BCC — XOR of ALL characters including % prefix.
    Per document: XOR from % to last text char inclusive.
    """
    result = 0
    for c in frame:
        result ^= ord(c)
    return f'{result:02X}'


def _build_write_cmd(k_value: int) -> bytes:
    """
    Build MEWTOCOL WD command for DT register write.
    """
    addr = f'{PLC_DT_SETPOINT:05d}'
    
    # FIX 1: Convert to 16-bit Little-Endian (Low Byte first, then High Byte)
    val_16bit = k_value & 0xFFFF
    low_byte = val_16bit & 0xFF
    high_byte = (val_16bit >> 8) & 0xFF
    le_value = f'{low_byte:02X}{high_byte:02X}' # 1000 transforms from 03E8 into E803
    
    frame = f'%{PLC_UNIT}#WDD{addr}{addr}{le_value}'
    cmd = f'{frame}{_bcc(frame)}\r'.encode('ascii')
    print(f'PLC: write cmd: {repr(cmd)}')
    return cmd


def _parse_response(resp: bytes) -> bool:
    """Parse MEWTOCOL write response."""
    if not resp:
        return False
    text = resp.decode('ascii', errors='ignore').strip()
    if '$WD' in text:
        return True
    if '!' in text:
        print(f'PLC: MEWTOCOL error response: {text}')
        return False
    return False


class PlcComms:
    def __init__(self):
        self._serial = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        port = settings.get('plc_port')
        if not port:
            print('PLC: plc_port not configured')
            return False
        try:
            self._serial = serial.Serial(
                port = port,
                baudrate = PLC_BAUD,
                bytesize = PLC_BYTESIZE,
                parity = PLC_PARITY,
                stopbits = PLC_STOPBITS,
                timeout = PLC_TIMEOUT,
            )
            self._connected = True
            print(f'PLC: connected on {port}')
            return True
        except Exception as e:
            print(f'PLC: connect failed — {e}')
            self._connected = False
            return False

    def disconnect(self):
        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._serial is not None

    def set_k(self, k_value: int) -> bool:
        """Write K value (0-4000) to PLC DT100."""
        if not self.is_connected():
            print('PLC.set_k: not connected')
            return False
        if not isinstance(k_value, int):
            print(f'PLC.set_k: expected int, got {type(k_value)}')
            return False
        if not PLC_K_MIN <= k_value <= PLC_K_MAX:
            print(f'PLC.set_k: {k_value} out of range [{PLC_K_MIN}, {PLC_K_MAX}]')
            return False
            
        cmd = _build_write_cmd(k_value)
        success = False
        
        for attempt in range(PLC_MAX_RETRIES):
            try:
                with self._lock:
                    self._serial.reset_input_buffer()
                    self._serial.write(cmd)
                    resp = self._serial.read_until(b'\r')
                    self._serial.reset_input_buffer()
                
                if _parse_response(resp):
                    success = True
                    break # Break out of loop immediately on success
                    
                print(f'PLC: set_k attempt {attempt + 1} bad response: {resp}')
            except Exception as e:
                print(f'PLC: set_k attempt {attempt + 1} failed — {e}')
            time.sleep(PLC_RETRY_DELAY)
            
        # FIX 2: Enforce the inter-command cool-down delay HERE 
        # so it executes for consecutive external loop queries.
        time.sleep(0.05) 
        return success

    def emergency_off(self) -> bool:
        return self.set_k(0)

    def read_dt(self, addr: int):
        """Read one DT register. Returns properly byte-swapped integer or None."""
        if not self.is_connected():
            return None
        frame = f'%{PLC_UNIT}#RDD{addr:05d}{addr:05d}'
        cmd = f'{frame}{_bcc(frame)}\r'.encode('ascii')
        print(f'PLC: sending: {repr(cmd)}')
        
        try:
            with self._lock:
                self._serial.reset_input_buffer()
                self._serial.write(cmd)
                raw = self._serial.read_until(b'\r')
                self._serial.reset_input_buffer()
                
            time.sleep(0.05) # Inter-command hardware gap
            print(f'PLC: read_dt({addr}) raw: {repr(raw)}')
            text = raw.decode('ascii', errors='ignore').strip()
            
            if '$RD' in text:
                idx = text.index('$RD') + 3
                raw_hex = text[idx:idx+4] # Example: yields 'E803'
                
                # FIX 3: Re-swap Little-Endian hex bytes back to proper Big-Endian int
                low_byte = int(raw_hex[0:2], 16)
                high_byte = int(raw_hex[2:4], 16)
                actual_value = (high_byte << 8) | low_byte
                
                # Handle signed 16-bit negative values if needed
                if actual_value & 0x8000:
                    actual_value -= 0x10000
                    
                return actual_value
                
            if '!' in text:
                print(f'PLC: read_dt error response: {text}')
            return None
        except Exception as e:
            print(f'PLC: read_dt failed — {e}')
            return None

