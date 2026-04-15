# =============================================================================
# translations.py — UI string translations
# =============================================================================
# Supports: English (en), Simplified Chinese (zh), Malay (ms)
# Usage:
#   from translations import tr
#   label.setText(tr('inlet_temp'))
# =============================================================================

from settings_manager import settings

STRINGS = {
    # ── Tab names ─────────────────────────────────────────────────────────────
    'tab_monitor':      {'en': 'MONITOR',           'zh': '监控',           'ms': 'MONITOR'},
    'tab_test':         {'en': 'HEAT LOAD TEST',    'zh': '热负载测试',      'ms': 'UJI BEBAN HABA'},
    'tab_settings':     {'en': 'SETTINGS',          'zh': '设置',           'ms': 'TETAPAN'},
    'tab_docs':         {'en': 'DOCUMENTATION',     'zh': '文档',           'ms': 'DOKUMENTASI'},

    # ── Monitor tab ───────────────────────────────────────────────────────────
    'live_readings':    {'en': 'LIVE READINGS',     'zh': '实时读数',        'ms': 'BACAAN LANGSUNG'},
    'inlet_temp':       {'en': 'INLET TEMP (TCU)',  'zh': '进水温度 (TCU)',  'ms': 'SUHU MASUK (TCU)'},
    'setpoint':         {'en': 'SETPOINT',          'zh': '设定值',          'ms': 'TITIK TETAP'},
    'flow_rate':        {'en': 'FLOW RATE',         'zh': '流量',            'ms': 'KADAR ALIRAN'},
    'voltage':          {'en': 'VOLTAGE (PZEM004T)','zh': '电压 (PZEM004T)', 'ms': 'VOLTAN (PZEM004T)'},
    'current':          {'en': 'CURRENT (PZEM004T)','zh': '电流 (PZEM004T)', 'ms': 'ARUS (PZEM004T)'},
    'power':            {'en': 'POWER (PZEM004T)',  'zh': '功率 (PZEM004T)', 'ms': 'KUASA (PZEM004T)'},
    'alarm_status':     {'en': 'ALARM STATUS',      'zh': '报警状态',        'ms': 'STATUS PENGGERA'},
    'no_alarms':        {'en': '✓  No alarms',      'zh': '✓  无报警',       'ms': '✓  Tiada penggera'},
    'temp_trend':       {'en': 'TEMPERATURE TREND (LAST 10 MIN)', 'zh': '温度趋势 (最近10分钟)', 'ms': 'TREND SUHU (10 MINIT LEPAS)'},
    'tcu_controls':     {'en': 'TCU CONTROLS',      'zh': 'TCU 控制',        'ms': 'KAWALAN TCU'},
    'set_setpoint':     {'en': 'SET SETPOINT',      'zh': '设置目标值',       'ms': 'TETAP TITIK SASARAN'},
    'cmd_log':          {'en': 'COMMAND LOG  (RS232)', 'zh': '命令日志 (RS232)', 'ms': 'LOG ARAHAN (RS232)'},
    'alarm_history':    {'en': 'ALARM HISTORY',     'zh': '报警历史',        'ms': 'SEJARAH PENGGERA'},
    'btn_start':        {'en': 'START',             'zh': '启动',            'ms': 'MULA'},
    'btn_stop':         {'en': 'STOP',              'zh': '停止',            'ms': 'BERHENTI'},
    'btn_fill':         {'en': 'FILL  (AFV)',        'zh': '注水 (AFV)',      'ms': 'ISI  (AFV)'},
    'btn_precond':      {'en': 'PRECOND  (VT)',      'zh': '预调温 (VT)',     'ms': 'PRAKONDISI  (VT)'},
    'btn_clr_alarm':    {'en': 'CLEAR ALARM  (ER)', 'zh': '清除报警 (ER)',   'ms': 'BERSIH PENGGERA  (ER)'},
    'btn_close_valve':  {'en': 'CLOSE VALVE  (CVE)','zh': '关阀 (CVE)',      'ms': 'TUTUP INJAP  (CVE)'},
    'btn_set':          {'en': 'SET',               'zh': '设置',            'ms': 'TETAP'},
    'connected':        {'en': '● CONNECTED',       'zh': '● 已连接',        'ms': '● DISAMBUNG'},
    'disconnected':     {'en': '● DISCONNECTED',    'zh': '● 未连接',        'ms': '● TIDAK DISAMBUNG'},

    # ── Test tab ──────────────────────────────────────────────────────────────
    'elapsed':          {'en': 'ELAPSED',           'zh': '已用时间',        'ms': 'MASA BERLALU'},
    'remaining':        {'en': 'REMAINING',         'zh': '剩余时间',        'ms': 'MASA BAKI'},
    'alarms':           {'en': 'ALARMS',            'zh': '报警',            'ms': 'PENGGERA'},
    'tcu_serial':       {'en': 'TCU SERIAL NUMBER', 'zh': 'TCU 序列号',      'ms': 'NOMBOR SIRI TCU'},
    'serial_ph':        {'en': 'e.g. ASM-001234',   'zh': '例：ASM-001234',  'ms': 'cth. ASM-001234'},
    'test_controls':    {'en': 'TEST CONTROLS',     'zh': '测试控制',        'ms': 'KAWALAN UJIAN'},
    'btn_test_start':   {'en': '▶  START TEST',     'zh': '▶  开始测试',     'ms': '▶  MULA UJIAN'},
    'btn_test_stop':    {'en': '■  ABORT TEST',     'zh': '■  中止测试',     'ms': '■  HENTI UJIAN'},
    'pass_criteria':    {'en': 'PASS / FAIL CRITERIA', 'zh': '通过/失败标准', 'ms': 'KRITERIA LULUS/GAGAL'},
    'test_result':      {'en': 'TEST RESULT',       'zh': '测试结果',        'ms': 'KEPUTUSAN UJIAN'},
    'log_file':         {'en': 'LOG FILE',          'zh': '日志文件',        'ms': 'FAIL LOG'},
    'not_started':      {'en': 'Not started',       'zh': '未开始',          'ms': 'Belum bermula'},
    'ready_msg':        {'en': 'READY — ENTER SERIAL NUMBER AND PRESS START TEST',
                         'zh': '就绪 — 输入序列号并按开始测试',
                         'ms': 'SEDIA — MASUKKAN NOMBOR SIRI DAN TEKAN MULA UJIAN'},
    'test_running':     {'en': '● TEST RUNNING — DO NOT DISCONNECT',
                         'zh': '● 测试进行中 — 请勿断开',
                         'ms': '● UJIAN BERJALAN — JANGAN PUTUSKAN SAMBUNGAN'},
    'enter_serial':     {'en': '⚠  ENTER TCU SERIAL NUMBER FIRST',
                         'zh': '⚠  请先输入TCU序列号',
                         'ms': '⚠  MASUKKAN NOMBOR SIRI TCU DAHULU'},

    # ── Settings tab ──────────────────────────────────────────────────────────
    'settings_serial':  {'en': 'SERIAL PORTS',      'zh': '串口设置',        'ms': 'PORT BERSIRI'},
    'settings_test':    {'en': 'TEST PARAMETERS',   'zh': '测试参数',        'ms': 'PARAMETER UJIAN'},
    'settings_ui':      {'en': 'DISPLAY & LANGUAGE', 'zh': '显示与语言',     'ms': 'PAPARAN & BAHASA'},
    'tcu_port_lbl':     {'en': 'TCU Port',          'zh': 'TCU 端口',        'ms': 'Port TCU'},
    'tcu_baud_lbl':     {'en': 'TCU Baud Rate',     'zh': 'TCU 波特率',      'ms': 'Kadar Baud TCU'},
    'pzem_port_lbl':    {'en': 'PZEM Port',         'zh': 'PZEM 端口',       'ms': 'Port PZEM'},
    'pzem_baud_lbl':    {'en': 'PZEM Baud Rate',    'zh': 'PZEM 波特率',     'ms': 'Kadar Baud PZEM'},
    'temp_sp_lbl':      {'en': 'Temperature Setpoint (°C)', 'zh': '温度设定值 (°C)', 'ms': 'Titik Tetap Suhu (°C)'},
    'temp_tol_lbl':     {'en': 'Temperature Tolerance (°C)', 'zh': '温度容差 (°C)', 'ms': 'Toleransi Suhu (°C)'},
    'test_dur_lbl':     {'en': 'Test Duration (min)', 'zh': '测试时长 (分钟)', 'ms': 'Tempoh Ujian (min)'},
    'poll_int_lbl':     {'en': 'Poll Interval (sec)', 'zh': '轮询间隔 (秒)',  'ms': 'Selang Tinjauan (saat)'},
    'theme_lbl':        {'en': 'Display Theme',     'zh': '显示主题',        'ms': 'Tema Paparan'},
    'theme_light':      {'en': 'Light',             'zh': '浅色',            'ms': 'Cerah'},
    'theme_dark':       {'en': 'Dark',              'zh': '深色',            'ms': 'Gelap'},
    'language_lbl':     {'en': 'Language',          'zh': '语言',            'ms': 'Bahasa'},
    'btn_apply':        {'en': 'APPLY',             'zh': '应用',            'ms': 'GUNA'},
    'btn_reset':        {'en': 'RESET TO DEFAULTS', 'zh': '恢复默认',        'ms': 'TETAPKAN SEMULA'},
    'applied_ok':       {'en': '✓ Settings applied', 'zh': '✓ 设置已应用',   'ms': '✓ Tetapan diguna'},
    'restart_note':     {'en': 'Note: Port changes take effect on next connection',
                         'zh': '注意：端口更改在下次连接时生效',
                         'ms': 'Nota: Perubahan port berkuat kuasa pada sambungan seterusnya'},
}


def tr(key: str) -> str:
    """Return the translated string for the current language setting."""
    lang = settings.get('language', 'en')
    entry = STRINGS.get(key, {})
    return entry.get(lang, entry.get('en', key))
