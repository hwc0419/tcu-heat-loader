# =============================================================================
# audit_logger.py — Circular Buffer Audit Logger
# =============================================================================
# Logs safety-critical user actions to daily CSV files in .keylogger/
# One file per day, 1MB daily limit, circular buffer (oldest overwritten).
# Users are not informed of logging. Folder is hidden at OS level.
# =============================================================================

import csv
import os
import threading
from datetime import datetime

_AUDIT_DIR    = '.keylogger'
_MAX_BYTES    = 1 * 1024 * 1024   # 1MB per day
_HEADERS      = ['timestamp', 'source', 'user', 'action', 'value']
_lock         = threading.Lock()


def _today_path() -> str:
    date_str = datetime.now().strftime('%Y%m%d')
    return os.path.join(_AUDIT_DIR, f'audit_{date_str}.csv')


def _ensure_dir():
    os.makedirs(_AUDIT_DIR, exist_ok=True)


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def _read_rows(path: str) -> list:
    """Read all rows from CSV. Returns empty list if file missing."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        return rows
    except Exception as e:
        print(f"AuditLogger: read error — {e}")
        return []


def _write_rows(path: str, rows: list):
    """Write rows to CSV including header."""
    try:
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(_HEADERS)
            writer.writerows(rows)
    except Exception as e:
        print(f"AuditLogger: write error — {e}")


def _new_row(source: str, user: str, action: str, value: str) -> list:
    return [
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        source, user, action, value
    ]


def log(source: str, user: str, action: str, value: str = ''):
    """
    Append one audit entry. Thread-safe.

    Args:
        source: 'Desktop' or 'Web:<username>'
        user:   username or 'desktop'
        action: human-readable action string
        value:  associated value (e.g. '5000W', '22.0°C')
    """
    if not isinstance(source, str) or not isinstance(user, str):
        return
    if not isinstance(action, str) or not isinstance(value, str):
        return

    _ensure_dir()
    path = _today_path()
    row  = _new_row(source, user, action, value)

    with _lock:
        rows = _read_rows(path)
        # Strip header row if present
        data = [r for r in rows if r and r[0] != 'timestamp']
        data.append(row)

        # Circular buffer — drop oldest row if over limit
        _write_rows(path, data)
        while _file_size(path) > _MAX_BYTES and len(data) > 1:
            data.pop(0)
            _write_rows(path, data)
