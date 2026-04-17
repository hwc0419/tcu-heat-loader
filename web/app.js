// =============================================================================
// app.js — TCU++ Web Dashboard Frontend Logic
// =============================================================================

// ── State ─────────────────────────────────────────────────────────────────────
let me = null;                  // current user {username, name, role}
let hasLock = false;            // whether current user has operator lock
let testRunning = false;        // whether a test is in progress
let testStartTime = null;       // epoch seconds when test started
let testDuration = 180;         // minutes (loaded from server data)
let pollInterval = null;        // setInterval handle
let monitorTimes = [];          // graph data — timestamps (minutes)
let monitorTemps = [];          // graph data — inlet temps
let monitorPowers = [];         // graph data — power values
let testTimes = [];
let testTemps = [];
let testPowers = [];
const MAX_MONITOR_POINTS = 600; // 10 min at 1Hz

// ── Charts ────────────────────────────────────────────────────────────────────
let monitorChart = null;
let testChart    = null;

function initCharts() {
  const commonOptions = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: true, labels: { font: { family: 'Courier New', size: 10 } } } },
    scales: {
      x: { ticks: { font: { family: 'Courier New', size: 9 } }, grid: { color: '#EEEEEE' } },
      y: { ticks: { font: { family: 'Courier New', size: 9 } }, grid: { color: '#EEEEEE' } },
    }
  };

  monitorChart = new Chart(document.getElementById('monitor-graph'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'TCU Inlet (°C)', data: [], borderColor: '#0077B6', borderWidth: 2,
          pointRadius: 0, tension: 0.1, yAxisID: 'y' },
        { label: 'Power (W)',      data: [], borderColor: '#B8860B', borderWidth: 1,
          pointRadius: 0, tension: 0.1, yAxisID: 'y2' },
      ]
    },
    options: {
      ...commonOptions,
      scales: {
        ...commonOptions.scales,
        y:  { ...commonOptions.scales.y, position: 'left',  title: { display: true, text: '°C', font: { family: 'Courier New', size: 9 } } },
        y2: { position: 'right', grid: { drawOnChartArea: false },
               ticks: { font: { family: 'Courier New', size: 9 } },
               title: { display: true, text: 'W', font: { family: 'Courier New', size: 9 } } },
      }
    }
  });

  testChart = new Chart(document.getElementById('test-graph'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'TCU Inlet (°C)', data: [], borderColor: '#0077B6', borderWidth: 2,
          pointRadius: 0, tension: 0.1, yAxisID: 'y' },
        { label: 'Power (W)',      data: [], borderColor: '#B8860B', borderWidth: 1,
          pointRadius: 0, tension: 0.1, yAxisID: 'y2' },
      ]
    },
    options: {
      ...commonOptions,
      scales: {
        ...commonOptions.scales,
        x: { ...commonOptions.scales.x, title: { display: true, text: 'Elapsed (min)', font: { family: 'Courier New', size: 9 } } },
        y:  { ...commonOptions.scales.y, position: 'left',  title: { display: true, text: '°C', font: { family: 'Courier New', size: 9 } } },
        y2: { position: 'right', grid: { drawOnChartArea: false },
               ticks: { font: { family: 'Courier New', size: 9 } },
               title: { display: true, text: 'W', font: { family: 'Courier New', size: 9 } } },
      }
    }
  });
}

// ── Auth ──────────────────────────────────────────────────────────────────────
async function loadMe() {
  const res = await fetch('/api/me');
  const data = await res.json();
  if (!data.authenticated) {
    window.location.href = '/';
    return;
  }
  me = data;
  document.getElementById('user-name').textContent = `${data.name} (${data.role})`;
  if (data.role !== 'technician') {
    document.getElementById('controls-card').style.display = 'none';
    document.getElementById('test-controls-card').style.display = 'none';
  }
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/';
}

// ── Data polling ──────────────────────────────────────────────────────────────
async function poll() {
  try {
    const res = await fetch('/api/data');
    if (res.status === 401) { window.location.href = '/'; return; }

    if (!res.ok) {
      // DAQ unavailable — still update lock and connection status
      setOffline();
      await pollLock();
      return;
    }

    const data = await res.json();
    setOnline();
    updateReadings(data);
    updateLockUI(data.lock);
    updateGraphs(data);
    checkAlarms(data);

  } catch {
    setOffline();
    await pollLock();
  }
}

async function pollLock() {
  try {
    const res = await fetch('/api/lock/status');
    if (res.status === 401) { window.location.href = '/'; return; }
    if (res.ok) {
      const lock = await res.json();
      updateLockUI(lock);
    }
  } catch {
    // ignore — lock UI stays at last known state
  }
}

function setOnline() {
  document.querySelector('#conn-indicator .conn-dot').className = 'conn-dot online';
  document.getElementById('conn-text').textContent = 'Live';
}

function setOffline() {
  document.querySelector('#conn-indicator .conn-dot').className = 'conn-dot offline';
  document.getElementById('conn-text').textContent = 'Offline';
}

// ── Readings update ───────────────────────────────────────────────────────────
function fmt(val, unit, decimals=2) {
  return val !== null && val !== undefined ? `${val.toFixed(decimals)} ${unit}` : '---';
}

function updateReadings(data) {
  // Monitor tab
  document.getElementById('val-inlet').textContent    = fmt(data.inlet_temp, '°C');
  document.getElementById('val-setpoint').textContent = fmt(data.setpoint, '°C');
  document.getElementById('val-flow').textContent     = fmt(data.flow_rate, 'ℓ/min', 1);
  document.getElementById('val-voltage').textContent  = fmt(data.voltage, 'V', 1);
  document.getElementById('val-current').textContent  = fmt(data.current, 'A', 3);
  document.getElementById('val-power').textContent    = fmt(data.power, 'W', 0);

  // Test tab
  document.getElementById('val-test-inlet').textContent    = fmt(data.inlet_temp, '°C');
  document.getElementById('val-test-setpoint').textContent = fmt(data.setpoint, '°C');
  document.getElementById('val-test-flow').textContent     = fmt(data.flow_rate, 'ℓ/min', 1);
  document.getElementById('val-test-voltage').textContent  = fmt(data.voltage, 'V', 1);
  document.getElementById('val-test-current').textContent  = fmt(data.current, 'A', 3);
  document.getElementById('val-test-power').textContent    = fmt(data.power, 'W', 0);

  // Alarm banner
  const alarms = data.alarms || ['No alarms'];
  const banner = document.getElementById('alarm-banner');
  if (alarms.length === 1 && alarms[0] === 'No alarms') {
    banner.className = 'alarm-banner ok';
    banner.textContent = '✓ No alarms';
    document.getElementById('val-test-alarms').textContent = '✓ No alarms';
  } else {
    banner.className = 'alarm-banner alarm';
    banner.textContent = '⚠ ' + alarms.join(' | ');
    document.getElementById('val-test-alarms').textContent = alarms[0];
  }

  // Test progress
  if (testRunning && testStartTime) {
    const elapsed = (Date.now() / 1000 - testStartTime) / 60;
    const pct = Math.min(100, (elapsed / testDuration) * 100);
    document.getElementById('test-progress').style.width = pct + '%';
    document.getElementById('val-elapsed').textContent   = elapsed.toFixed(1) + ' min';
    document.getElementById('val-remaining').textContent = Math.max(0, testDuration - elapsed).toFixed(1) + ' min';
  }

  // Criteria text
  if (data.setpoint) {
    document.getElementById('criteria-text').innerHTML =
      `✓ Inlet temp ${data.setpoint.toFixed(1)}°C ±0.5°C for full ${testDuration} min<br>` +
      `✓ Flow rate ≥ 1 ℓ/min continuously<br>` +
      `✓ No TCU alarms (BS = 400400)<br>` +
      `✓ Test duration ${testDuration} min completed`;
  }
}

// ── Graph update ──────────────────────────────────────────────────────────────
let graphT0 = null;

function updateGraphs(data) {
  const now = data.timestamp || (Date.now() / 1000);
  if (!graphT0) graphT0 = now;
  const elapsedMin = (now - graphT0) / 60;

  // Monitor graph — rolling 10 min
  monitorTimes.push(elapsedMin.toFixed(1));
  monitorTemps.push(data.inlet_temp);
  monitorPowers.push(data.power);
  if (monitorTimes.length > MAX_MONITOR_POINTS) {
    monitorTimes.shift(); monitorTemps.shift(); monitorPowers.shift();
  }
  monitorChart.data.labels           = monitorTimes;
  monitorChart.data.datasets[0].data = monitorTemps;
  monitorChart.data.datasets[1].data = monitorPowers;
  monitorChart.update('none');

  // Test graph — full test duration
  if (testRunning) {
    testTimes.push(elapsedMin.toFixed(1));
    testTemps.push(data.inlet_temp);
    testPowers.push(data.power);
    testChart.data.labels           = testTimes;
    testChart.data.datasets[0].data = testTemps;
    testChart.data.datasets[1].data = testPowers;
    testChart.update('none');
  }
}

// ── Alarm watcher ─────────────────────────────────────────────────────────────
let lastAlarms = ['No alarms'];

function checkAlarms(data) {
  const alarms = data.alarms || ['No alarms'];
  if (JSON.stringify(alarms) !== JSON.stringify(lastAlarms)) {
    if (!(alarms.length === 1 && alarms[0] === 'No alarms')) {
      showToast('⚠ ALARM: ' + alarms[0], 'red');
    }
    lastAlarms = alarms;
  }
}

// ── Lock management ───────────────────────────────────────────────────────────
function updateLockUI(lock) {
  if (!me) return;
  if (me.role !== 'technician') return;
  if (!lock) return;

  hasLock = lock.owner === me.username;
  const isTouchscreen = lock.owner === 'touchscreen';
  const myQueuePos = lock.queue ? lock.queue.findIndex(q => q.username === me.username) : -1;

  const updatePanel = (textId, acquireId, releaseId, statusId) => {
    const el    = document.getElementById(textId);
    const acq   = document.getElementById(acquireId);
    const rel   = document.getElementById(releaseId);
    const panel = document.getElementById(statusId);

    if (hasLock) {
      el.textContent    = '● You have control';
      panel.className   = 'lock-status mine';
      acq.style.display = 'none';
      rel.style.display = 'inline-flex';
    } else if (isTouchscreen) {
      el.textContent    = 'Touchscreen has priority control';
      panel.className   = 'lock-status other';
      acq.style.display = 'inline-flex';
      rel.style.display = 'none';
    } else if (lock.owner) {
      const pos = myQueuePos >= 0 ? ` — you are #${myQueuePos + 1} in queue` : '';
      el.textContent    = `Control locked by ${lock.owner_name}${pos}`;
      panel.className   = 'lock-status other';
      acq.style.display = myQueuePos < 0 ? 'inline-flex' : 'none';
      rel.style.display = 'none';
    } else {
      el.textContent    = 'No operator has control';
      panel.className   = 'lock-status';
      acq.style.display = 'inline-flex';
      rel.style.display = 'none';
    }
  };

  updatePanel('lock-text-monitor', 'btn-acquire-monitor', 'btn-release-monitor', 'lock-status-monitor');
  updatePanel('lock-text-test',    'btn-acquire-test',    'btn-release-test',    'lock-status-test');

  // Disable controls if no lock
  document.querySelectorAll('#tcu-controls .btn, #test-controls-card .btn-green, #test-controls-card .btn-red').forEach(btn => {
    btn.disabled = !hasLock;
  });
}

async function acquireLock() {
  const res = await fetch('/api/lock/acquire', { method: 'POST' });
  const data = await res.json();
  if (data.acquired) {
    showToast('✓ You now have control of the TCU', 'green');
  } else {
    showToast(`Control locked — you are #${data.position} in queue`, 'red');
  }
}

async function releaseLock() {
  await fetch('/api/lock/release', { method: 'POST' });
  showToast('Control released', 'green');
}

// ── TCU commands ──────────────────────────────────────────────────────────────
async function tcuCmd(cmd) {
  if (!hasLock) { showToast('Acquire control first', 'red'); return; }
  const res = await fetch(`/api/tcu/${cmd}`, { method: 'POST' });
  if (!res.ok) {
    const d = await res.json();
    showToast(d.error || 'Command failed', 'red');
  }
}

async function setSetpoint() {
  if (!hasLock) { showToast('Acquire control first', 'red'); return; }
  const temp = parseFloat(document.getElementById('setpoint-input').value);
  const res = await fetch('/api/tcu/setpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ temp })
  });
  if (!res.ok) {
    const d = await res.json();
    showToast(d.error || 'Failed to set setpoint', 'red');
  }
}

// ── Test controls ─────────────────────────────────────────────────────────────
async function startTest() {
  if (!hasLock) { showToast('Acquire control first', 'red'); return; }
  const serial = document.getElementById('test-serial').value.trim();
  if (!serial) { showToast('Enter TCU serial number first', 'red'); return; }

  const res = await fetch('/api/test/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serial })
  });

  if (res.ok) {
    testRunning   = true;
    testStartTime = Date.now() / 1000;
    testTimes     = [];
    testTemps     = [];
    testPowers    = [];
    document.getElementById('test-banner').className  = 'test-banner running';
    document.getElementById('test-banner').textContent = '● TEST RUNNING — DO NOT DISCONNECT';
    document.getElementById('test-result').textContent        = '—';
    document.getElementById('test-result-reason').textContent = '';
    showToast('✓ Test started — ' + serial, 'green');
  } else {
    const d = await res.json();
    showToast(d.error || 'Failed to start test', 'red');
  }
}

async function stopTest() {
  if (!hasLock) { showToast('Acquire control first', 'red'); return; }
  const res = await fetch('/api/test/stop', { method: 'POST' });
  if (res.ok) {
    testRunning = false;
    document.getElementById('test-banner').className  = 'test-banner';
    document.getElementById('test-banner').textContent = '■ TEST ABORTED';
    showToast('Test aborted', 'red');
  }
}

// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(message, type = 'green') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 500);
  }, 5000);
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

// ── Push notifications ────────────────────────────────────────────────────────
async function setupPushNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

  try {
    const reg = await navigator.serviceWorker.register('/sw.js');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;

    const res = await fetch('/api/push/vapid-public-key');
    if (!res.ok) return;
    const { public_key } = await res.json();

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key)
    });

    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sub)
    });
  } catch (e) {
    console.log('Push setup error:', e);
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64  = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw     = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

// ── Inactivity tracker ────────────────────────────────────────────────────────
let lastActivity = Date.now();

document.addEventListener('click',      () => lastActivity = Date.now());
document.addEventListener('touchstart', () => lastActivity = Date.now());
document.addEventListener('keydown',    () => lastActivity = Date.now());

setInterval(async () => {
  if (hasLock) {
    await fetch('/api/lock/activity', { method: 'POST' });
  }
}, 30000);  // ping every 30s if we have the lock

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  await loadMe();
  await pollLock();    // initialise lock UI immediately, don't wait for first poll
  initCharts();
  await setupPushNotifications();
  poll();
  pollInterval = setInterval(poll, 2000);
})();
