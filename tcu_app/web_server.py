# =============================================================================
# web_server.py — TCU++ Phone Web Dashboard Server
# =============================================================================
# Serves the TCU++ web dashboard to operators on the workshop WiFi.
# Runs as a SEPARATE PROCESS from the PyQt5 app.
#
# Access: http://tcuplusplus.local:5000
#
# Start: python3 web_server.py  (from tcu_app/ directory)
# Stop:  Ctrl+C
#
# Authentication:
#   Users managed in users.json
#   Roles: technician (full control), supervisor (view only)
#
# Operator lock:
#   Only one technician can control the TCU at a time.
#   Physical touchscreen always has priority.
#   Lock auto-releases after 5 min inactivity.
#   Queue is FIFO by login time.
# =============================================================================

import os
import sys
import json
import time
import hashlib
import threading
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, jsonify, session,
    send_from_directory, redirect, url_for, render_template_string
)

# ── IPC reader — reads live DAQ data from PyQt5 app process ──────────────────
sys.path.insert(0, os.path.dirname(__file__))
from ipc import IPCReader

# ── Flask app setup ───────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='../web', static_url_path='')
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=3)

WEB_DIR   = os.path.join(os.path.dirname(__file__), '..', 'web')
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
VAPID_FILE = os.path.join(os.path.dirname(__file__), 'vapid_keys.json')

ipc_reader = IPCReader()

# ── User management ───────────────────────────────────────────────────────────

def load_users() -> dict:
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_user(username: str, password: str) -> dict | None:
    users = load_users()
    user = users.get(username)
    if user and user['password'] == hash_password(password):
        return user
    return None

# ── Operator lock system ──────────────────────────────────────────────────────

class OperatorLock:
    """
    Manages which operator has control of the TCU.
    Physical touchscreen always has priority (lock_owner = 'touchscreen').
    Queue is FIFO by login time.
    Inactivity timeout: 5 minutes.
    """

    TIMEOUT_SECONDS = 300   # 5 minutes

    def __init__(self):
        self._lock       = threading.Lock()
        self._owner      = None    # username of current lock holder
        self._owner_name = None    # display name
        self._last_seen  = {}      # username -> last activity timestamp
        self._queue      = []      # list of (login_time, username, name) waiting
        self._lock_time  = None    # when lock was acquired

        # Start inactivity watcher
        t = threading.Thread(target=self._watch_inactivity, daemon=True)
        t.start()

    def _watch_inactivity(self):
        while True:
            time.sleep(10)
            with self._lock:
                if self._owner and self._owner != 'touchscreen':
                    last = self._last_seen.get(self._owner, 0)
                    if time.time() - last > self.TIMEOUT_SECONDS:
                        print(f'Lock: {self._owner} timed out — releasing')
                        self._release_locked()

    def _release_locked(self):
        """Release lock and give to next in queue. Must be called with _lock held."""
        self._owner      = None
        self._owner_name = None
        self._lock_time  = None
        self._promote_next()

    def _promote_next(self):
        """Give lock to next operator in queue."""
        if self._queue:
            _, username, name = self._queue.pop(0)
            self._owner      = username
            self._owner_name = name
            self._lock_time  = time.time()
            self._last_seen[username] = time.time()
            print(f'Lock: promoted {username} from queue')

    def try_acquire(self, username: str, display_name: str,
                    login_time: float) -> tuple[bool, int]:
        """
        Try to acquire control lock.
        Returns (acquired, queue_position) — position 0 means acquired.
        """
        with self._lock:
            # Already the owner
            if self._owner == username:
                self._last_seen[username] = time.time()
                return True, 0

            # Lock is free
            if self._owner is None:
                self._owner      = username
                self._owner_name = display_name
                self._lock_time  = time.time()
                self._last_seen[username] = time.time()
                return True, 0

            # Lock held by touchscreen or another user — join queue
            existing = [u for _, u, _ in self._queue]
            if username not in existing:
                self._queue.append((login_time, username, display_name))
                self._queue.sort(key=lambda x: x[0])   # FIFO by login time
            pos = next(i+1 for i, (_, u, _) in enumerate(self._queue)
                      if u == username)
            return False, pos

    def release(self, username: str):
        """Release lock voluntarily."""
        with self._lock:
            if self._owner == username:
                self._release_locked()

    def activity(self, username: str):
        """Update last activity timestamp."""
        with self._lock:
            self._last_seen[username] = time.time()

    def touchscreen_priority(self):
        """Physical touchscreen claims priority — overrides all web operators."""
        with self._lock:
            if self._owner != 'touchscreen':
                if self._owner:
                    self._queue.insert(0, (0, self._owner, self._owner_name))
                self._owner      = 'touchscreen'
                self._owner_name = 'Touchscreen'
                self._lock_time  = time.time()

    def touchscreen_release(self):
        """Physical touchscreen releases — restore web operator queue."""
        with self._lock:
            if self._owner == 'touchscreen':
                self._release_locked()

    def status(self) -> dict:
        with self._lock:
            return {
                'owner':      self._owner,
                'owner_name': self._owner_name,
                'queue':      [{'username': u, 'name': n}
                               for _, u, n in self._queue],
                'locked':     self._owner is not None,
            }

    def remove_from_queue(self, username: str):
        """Remove operator from queue (on logout)."""
        with self._lock:
            self._queue = [(t, u, n) for t, u, n in self._queue
                          if u != username]
            if self._owner == username:
                self._release_locked()


operator_lock = OperatorLock()

# ── Push notification subscription store ─────────────────────────────────────

subscriptions = []   # list of push subscription dicts
subscriptions_lock = threading.Lock()

def send_push_to_all(title: str, body: str, icon: str = '/icon.png'):
    """Send Web Push notification to all registered subscribers."""
    try:
        from pywebpush import webpush, WebPushException
        vapid = _load_vapid()
        if not vapid:
            return
        with subscriptions_lock:
            subs = list(subscriptions)
        for sub in subs:
            try:
                webpush(
                    subscription_info=sub,
                    data=json.dumps({'title': title, 'body': body, 'icon': icon}),
                    vapid_private_key=vapid['private_key'],
                    vapid_claims={'sub': 'mailto:admin@tcuplusplus.local'}
                )
            except WebPushException as e:
                if '410' in str(e) or '404' in str(e):
                    with subscriptions_lock:
                        if sub in subscriptions:
                            subscriptions.remove(sub)
    except Exception as e:
        print(f'Push error: {e}')

def _load_vapid() -> dict | None:
    try:
        with open(VAPID_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print('VAPID keys not found — run generate_vapid.py first')
        return None

# ── Auth decorator ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated

def technician_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        if session.get('role') != 'technician':
            return jsonify({'error': 'Technician role required'}), 403
        return f(*args, **kwargs)
    return decorated

# ── Active sessions tracker (for lock queue ordering) ────────────────────────
active_sessions = {}   # username -> login_time
active_sessions_lock = threading.Lock()

# =============================================================================
# Routes — Static files
# =============================================================================

@app.route('/')
def index():
    if 'username' in session:
        return send_from_directory(WEB_DIR, 'dashboard.html')
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')
    return send_from_directory(WEB_DIR, 'dashboard.html')

# =============================================================================
# Routes — Authentication
# =============================================================================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    remember = data.get('remember', False)

    user = verify_user(username, password)
    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401

    session.permanent = True
    session['username']     = username
    session['name']         = user['name']
    session['role']         = user['role']
    session['login_time']   = time.time()

    with active_sessions_lock:
        active_sessions[username] = time.time()

    return jsonify({
        'username': username,
        'name':     user['name'],
        'role':     user['role'],
    })

@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    username = session.get('username')
    operator_lock.release(username)
    operator_lock.remove_from_queue(username)
    with active_sessions_lock:
        active_sessions.pop(username, None)
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def api_me():
    if 'username' not in session:
        return jsonify({'authenticated': False})
    return jsonify({
        'authenticated': True,
        'username':      session['username'],
        'name':          session['name'],
        'role':          session['role'],
    })

# =============================================================================
# Routes — Live data
# =============================================================================

@app.route('/api/data')
@login_required
def api_data():
    """Return latest DAQ sample from IPC."""
    operator_lock.activity(session['username'])
    data = ipc_reader.read()
    if data is None:
        return jsonify({'error': 'No data available — PyQt5 app may not be running'}), 503
    data['lock'] = operator_lock.status()
    data['server_time'] = time.time()
    return jsonify(data)

# =============================================================================
# Routes — Operator lock
# =============================================================================

@app.route('/api/lock/acquire', methods=['POST'])
@technician_required
def api_lock_acquire():
    username = session['username']
    name     = session['name']
    with active_sessions_lock:
        login_time = active_sessions.get(username, time.time())

    acquired, position = operator_lock.try_acquire(username, name, login_time)
    return jsonify({
        'acquired': acquired,
        'position': position,
        'lock':     operator_lock.status(),
    })

@app.route('/api/lock/release', methods=['POST'])
@technician_required
def api_lock_release():
    operator_lock.release(session['username'])
    return jsonify({'ok': True, 'lock': operator_lock.status()})

@app.route('/api/lock/activity', methods=['POST'])
@login_required
def api_lock_activity():
    operator_lock.activity(session['username'])
    return jsonify({'ok': True})

@app.route('/api/lock/status')
@login_required
def api_lock_status():
    return jsonify(operator_lock.status())

# =============================================================================
# Routes — TCU commands (technician + lock required)
# =============================================================================

def _tcu_command(cmd_name: str) -> tuple[dict, int]:
    """Helper — checks lock ownership before forwarding command."""
    username = session.get('username')
    lock_status = operator_lock.status()
    if lock_status['owner'] != username:
        return {'error': 'You do not have control — acquire lock first'}, 403
    operator_lock.activity(username)
    # Commands are forwarded to PyQt5 app via a command queue file
    _write_command({'cmd': cmd_name, 'timestamp': time.time(), 'user': username})
    return {'ok': True, 'cmd': cmd_name}, 200

@app.route('/api/tcu/start', methods=['POST'])
@technician_required
def api_tcu_start():
    result, code = _tcu_command('START')
    return jsonify(result), code

@app.route('/api/tcu/stop', methods=['POST'])
@technician_required
def api_tcu_stop():
    result, code = _tcu_command('STOP')
    return jsonify(result), code

@app.route('/api/tcu/fill', methods=['POST'])
@technician_required
def api_tcu_fill():
    result, code = _tcu_command('AFV')
    return jsonify(result), code

@app.route('/api/tcu/precond', methods=['POST'])
@technician_required
def api_tcu_precond():
    result, code = _tcu_command('VT')
    return jsonify(result), code

@app.route('/api/tcu/clear_alarm', methods=['POST'])
@technician_required
def api_tcu_clear_alarm():
    result, code = _tcu_command('ER')
    return jsonify(result), code

@app.route('/api/tcu/close_valve', methods=['POST'])
@technician_required
def api_tcu_close_valve():
    result, code = _tcu_command('CVE')
    return jsonify(result), code

@app.route('/api/tcu/setpoint', methods=['POST'])
@technician_required
def api_tcu_setpoint():
    data = request.get_json()
    temp = data.get('temp')
    if temp is None:
        return jsonify({'error': 'temp required'}), 400
    try:
        temp = float(temp)
        if not 17.0 <= temp <= 27.0:
            return jsonify({'error': 'Setpoint must be 17.0–27.0°C'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid temperature'}), 400
    username = session.get('username')
    lock_status = operator_lock.status()
    if lock_status['owner'] != username:
        return jsonify({'error': 'You do not have control — acquire lock first'}), 403
    operator_lock.activity(username)
    _write_command({'cmd': 'SOLL', 'temp': temp,
                    'timestamp': time.time(), 'user': username})
    return jsonify({'ok': True, 'cmd': 'SOLL', 'temp': temp})

# =============================================================================
# Routes — Test control
# =============================================================================

@app.route('/api/test/start', methods=['POST'])
@technician_required
def api_test_start():
    data = request.get_json()
    serial = data.get('serial', '').strip()
    if not serial:
        return jsonify({'error': 'TCU serial number required'}), 400
    username = session.get('username')
    lock_status = operator_lock.status()
    if lock_status['owner'] != username:
        return jsonify({'error': 'You do not have control — acquire lock first'}), 403
    operator_lock.activity(username)
    _write_command({'cmd': 'TEST_START', 'serial': serial,
                    'timestamp': time.time(), 'user': username})
    return jsonify({'ok': True, 'serial': serial})

@app.route('/api/test/stop', methods=['POST'])
@technician_required
def api_test_stop():
    username = session.get('username')
    lock_status = operator_lock.status()
    if lock_status['owner'] != username:
        return jsonify({'error': 'You do not have control — acquire lock first'}), 403
    operator_lock.activity(username)
    _write_command({'cmd': 'TEST_STOP', 'timestamp': time.time(), 'user': username})
    return jsonify({'ok': True})

# =============================================================================
# Routes — Push notifications
# =============================================================================

@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def api_push_subscribe():
    sub = request.get_json()
    with subscriptions_lock:
        if sub not in subscriptions:
            subscriptions.append(sub)
    return jsonify({'ok': True})

@app.route('/api/push/vapid-public-key')
def api_vapid_public_key():
    vapid = _load_vapid()
    if not vapid:
        return jsonify({'error': 'VAPID keys not configured'}), 503
    return jsonify({'public_key': vapid['public_key']})

# =============================================================================
# Command queue — web server writes commands, PyQt5 app reads and executes
# =============================================================================

CMD_FILE = os.path.join(os.path.dirname(__file__), '.tcu_cmd.json')

def _write_command(cmd: dict):
    """Write command to command queue file for PyQt5 app to pick up."""
    try:
        tmp = CMD_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(cmd, f)
        os.replace(tmp, CMD_FILE)
    except Exception as e:
        print(f'Command write error: {e}')

# =============================================================================
# Alarm watcher — monitors IPC data and sends push notifications on alarms
# =============================================================================

class AlarmWatcher(threading.Thread):
    """
    Polls IPC data every 2 seconds.
    Sends push notifications when:
    - TCU alarms detected
    - BS status becomes abnormal
    """

    def __init__(self):
        super().__init__(daemon=True, name='AlarmWatcher')
        self._last_alarms    = ['No alarms']
        self._last_abnormal  = False

    def run(self):
        while True:
            time.sleep(2)
            try:
                data = ipc_reader.read()
                if not data:
                    continue

                alarms    = data.get('alarms', ['No alarms'])
                abnormal  = data.get('is_abnormal', False)

                # New alarms appeared
                if alarms != ['No alarms'] and alarms != self._last_alarms:
                    for alarm in alarms:
                        if alarm not in self._last_alarms:
                            send_push_to_all(
                                title='⚠ TCU++ Alarm',
                                body=alarm
                            )

                # Status became abnormal
                if abnormal and not self._last_abnormal:
                    decoded = data.get('decoded_log', [])
                    abnormal_lines = [l for l in decoded
                                     if l.startswith('⚠') or l.startswith('✕')]
                    if abnormal_lines:
                        send_push_to_all(
                            title='⚠ TCU++ Status Alert',
                            body=abnormal_lines[0]
                        )

                self._last_alarms   = alarms
                self._last_abnormal = abnormal

            except Exception as e:
                print(f'AlarmWatcher error: {e}')


# =============================================================================
# Entry point
# =============================================================================

if __name__ == '__main__':
    print('=' * 60)
    print('  TCU++ Web Server')
    print('  Access: http://tcuplusplus.local:5000')
    print('  Ctrl+C to stop')
    print('=' * 60)

    AlarmWatcher().start()

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
    )
