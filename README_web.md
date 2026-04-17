# TCU++ Web Dashboard

Browser-based monitoring and control dashboard for the TCU++ heat load test jig.
Accessible from any phone or laptop on the same workshop WiFi — no app installation needed.

## Access URL

```
http://tcuplusplus.local:5000
```

## First-time Setup (run once on RPi)

### 1. Install dependencies

```bash
cd tcu_app
pip install flask pywebpush cryptography
```

### 2. Generate VAPID keys (required for push notifications)

```bash
python3 generate_vapid.py
```

This creates `vapid_keys.json` in `tcu_app/`. Keep this file secure — do not commit to git.

### 3. Set up mDNS hostname (required for `tcuplusplus.local` to work)

```bash
sudo apt install avahi-daemon
sudo hostnamectl set-hostname tcuplusplus
sudo reboot
```

### 4. Grant notification permission on operator phones

When an operator first visits the dashboard, the browser will ask for notification permission. They must tap **Allow** to receive alarm push notifications.

## Starting the Web Server

The web server runs as a **separate process** from the PyQt5 desktop app. Both must be running for the web dashboard to show live data.

**Terminal 1 — PyQt5 desktop app:**
```bash
cd tcu_app
python3 main.py
```

**Terminal 2 — Web server:**
```bash
cd tcu_app
python3 web_server.py
```

The web server reads live data from the desktop app via IPC (`.tcu_ipc.json` on Windows, Unix socket on Linux).

## Managing Users

Users are stored in `tcu_app/users.json`. Passwords are SHA-256 hashed.

To add or change a user, run:

```python
import hashlib, json

# Load existing users
with open('tcu_app/users.json') as f:
    users = json.load(f)

# Add/update a user
users['newuser'] = {
    'password': hashlib.sha256('yourpassword'.encode()).hexdigest(),
    'role': 'technician',   # or 'supervisor'
    'name': 'New User'
}

# Save
with open('tcu_app/users.json', 'w') as f:
    json.dump(users, f, indent=2)
```

**Roles:**
- `technician` — full control (monitor + TCU commands + start/stop test)
- `supervisor` — view only (monitor only, no commands)

## Operator Lock System

- Only **one technician** can control the TCU at a time
- The **physical touchscreen always has priority** over web operators
- If the lock holder is inactive for **5 minutes**, the lock is automatically released
- Waiting operators are queued **FIFO by login time** — the longest-waiting operator gets control next
- When control is transferred, the new operator receives a **push notification** and a green toast on screen

## Default Credentials

| Username | Password | Role |
|----------|----------|------|
| howard | changeme123 | technician |
| supervisor | supervisor123 | supervisor |

**Change these passwords before deploying.**

## Files

```
tcu_app/
├── web_server.py       — Flask backend
├── ipc.py              — IPC abstraction (JSON/socket)
├── users.json          — User credentials (gitignored)
├── vapid_keys.json     — Push notification keys (gitignored)
├── generate_vapid.py   — Run once to generate VAPID keys
└── .tcu_cmd.json       — Command queue (runtime, gitignored)

web/
├── index.html          — Login page
├── dashboard.html      — Main dashboard
├── app.js              — Frontend logic
├── style.css           — Light mode styling
├── manifest.json       — PWA manifest
└── sw.js               — Service worker (push notifications)
```

## Add to Home Screen (PWA)

Operators can add TCU++ to their phone home screen for quick access:
- **Android (Chrome):** Menu → Add to Home Screen
- **iOS (Safari):** Share → Add to Home Screen

The app will appear as an icon and open in full-screen mode like a native app.
