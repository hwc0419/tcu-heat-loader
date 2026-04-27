# =============================================================================
# translations.py — UI string translations
# =============================================================================
# Supports: English (en), Simplified Chinese (zh)
# Usage:
#   from translations import tr
#   label.setText(tr('inlet_temp'))
# =============================================================================

from settings_manager import settings

STRINGS = {
    # ── Tab names ─────────────────────────────────────────────────────────────
    'tab_monitor':      {'en': 'MONITOR',               'zh': '监控'},
    'tab_test':         {'en': 'HEAT LOAD TEST',        'zh': '热负载测试'},
    'tab_settings':     {'en': 'SETTINGS',              'zh': '设置'},
    'tab_docs':         {'en': 'DOCUMENTATION',         'zh': '文档'},
    'tab_heater':       {'en': 'HEATER',                'zh': '加热器'},
    'tab_response':     {'en': 'RESPONSE TEST',         'zh': '响应测试'},

    # ── Monitor tab ───────────────────────────────────────────────────────────
    'live_readings':    {'en': 'LIVE READINGS',         'zh': '实时读数'},
    'inlet_temp':       {'en': 'INLET TEMP (TCU)',      'zh': '进水温度 (TCU)'},
    'setpoint':         {'en': 'SETPOINT',              'zh': '设定值'},
    'flow_rate':        {'en': 'FLOW RATE',             'zh': '流量'},
    'voltage':          {'en': 'VOLTAGE (PZEM004T)',    'zh': '电压 (PZEM004T)'},
    'current':          {'en': 'CURRENT (PZEM004T)',    'zh': '电流 (PZEM004T)'},
    'power':            {'en': 'POWER (PZEM004T)',      'zh': '功率 (PZEM004T)'},
    'alarm_status':     {'en': 'ALARM STATUS',          'zh': '报警状态'},
    'no_alarms':        {'en': '✓  No alarms',          'zh': '✓  无报警'},
    'temp_trend':       {'en': 'TEMPERATURE TREND (LAST 10 MIN)', 'zh': '温度趋势 (最近10分钟)'},
    'tcu_controls':     {'en': 'TCU CONTROLS',          'zh': 'TCU 控制'},
    'set_setpoint':     {'en': 'SET SETPOINT',          'zh': '设置目标值'},
    'cmd_log':          {'en': 'COMMAND LOG  (RS232)',  'zh': '命令日志 (RS232)'},
    'alarm_history':    {'en': 'ALARM HISTORY',         'zh': '报警历史'},
    'btn_start':        {'en': 'START',                 'zh': '启动'},
    'btn_stop':         {'en': 'STOP',                  'zh': '停止'},
    'btn_fill':         {'en': 'FILL  (AFV)',            'zh': '注水 (AFV)'},
    'btn_precond':      {'en': 'PRECOND  (VT)',          'zh': '预调温 (VT)'},
    'btn_clr_alarm':    {'en': 'CLEAR ALARM  (ER)',     'zh': '清除报警 (ER)'},
    'btn_close_valve':  {'en': 'CLOSE VALVE  (CVE)',    'zh': '关阀 (CVE)'},
    'btn_set':          {'en': 'SET',                   'zh': '设置'},
    'connected':        {'en': '● CONNECTED',           'zh': '● 已连接'},
    'disconnected':     {'en': '● DISCONNECTED',        'zh': '● 未连接'},

    # ── Test tab ──────────────────────────────────────────────────────────────
    'elapsed':          {'en': 'ELAPSED',               'zh': '已用时间'},
    'remaining':        {'en': 'REMAINING',             'zh': '剩余时间'},
    'alarms':           {'en': 'ALARMS',                'zh': '报警'},
    'tcu_serial':       {'en': 'TCU SERIAL NUMBER',     'zh': 'TCU 序列号'},
    'serial_ph':        {'en': 'e.g. ASM-001234',       'zh': '例：ASM-001234'},
    'test_controls':    {'en': 'TEST CONTROLS',         'zh': '测试控制'},
    'btn_test_start':   {'en': '▶  START TEST',         'zh': '▶  开始测试'},
    'btn_test_stop':    {'en': '■  ABORT TEST',         'zh': '■  中止测试'},
    'pass_criteria':    {'en': 'PASS / FAIL CRITERIA',  'zh': '通过/失败标准'},
    'test_result':      {'en': 'TEST RESULT',           'zh': '测试结果'},
    'log_file':         {'en': 'LOG FILE',              'zh': '日志文件'},
    'not_started':      {'en': 'Not started',           'zh': '未开始'},
    'ready_msg':        {'en': 'READY — ENTER SERIAL NUMBER AND PRESS START TEST',
                         'zh': '就绪 — 输入序列号并按开始测试'},
    'test_running':     {'en': '● TEST RUNNING — DO NOT DISCONNECT',
                         'zh': '● 测试进行中 — 请勿断开'},
    'enter_serial':     {'en': '⚠  ENTER TCU SERIAL NUMBER FIRST',
                         'zh': '⚠  请先输入TCU序列号'},

    # ── Settings tab — sub-tab labels ─────────────────────────────────────────
    'subtab_serial':        {'en': 'Serial',            'zh': '串口'},
    'subtab_post_repair':   {'en': 'Post-repair test',  'zh': '维修后测试'},
    'subtab_heater':        {'en': 'Heater',            'zh': '加热器'},
    'subtab_response_test': {'en': 'Response test',     'zh': '响应测试'},
    'subtab_advanced':      {'en': 'Advanced',          'zh': '高级'},

    # ── Settings tab — group box titles ───────────────────────────────────────
    'settings_serial':      {'en': 'SERIAL PORTS',      'zh': '串口设置'},
    'settings_test':        {'en': 'TEST PARAMETERS',   'zh': '测试参数'},
    'settings_ui':          {'en': 'DISPLAY & LANGUAGE','zh': '显示与语言'},
    'settings_heater_ctrl': {'en': 'HEATER CONTROL',    'zh': '加热器控制'},
    'settings_response':    {'en': 'RESPONSE TEST',     'zh': '响应测试'},

    # ── Settings tab — serial fields ──────────────────────────────────────────
    'tcu_port_lbl':         {'en': 'TCU Port',          'zh': 'TCU 端口'},
    'tcu_baud_lbl':         {'en': 'TCU Baud Rate',     'zh': 'TCU 波特率'},
    'pzem_port_lbl':        {'en': 'PZEM Port',         'zh': 'PZEM 端口'},
    'pzem_baud_lbl':        {'en': 'PZEM Baud Rate',    'zh': 'PZEM 波特率'},

    # ── Settings tab — post-repair test fields ────────────────────────────────
    'temp_sp_lbl':          {'en': 'Temperature Setpoint (°C)',     'zh': '温度设定值 (°C)'},
    'temp_tol_lbl':         {'en': 'Temperature Tolerance (°C)',    'zh': '温度容差 (°C)'},
    'test_dur_lbl':         {'en': 'Test Duration (min)',           'zh': '测试时长 (分钟)'},
    'poll_int_lbl':         {'en': 'Poll Interval (sec)',           'zh': '轮询间隔 (秒)'},

    # ── Settings tab — heater fields ──────────────────────────────────────────
    'heater_port_lbl':      {'en': 'Heater Port',           'zh': '加热器端口'},
    'heater_baud_lbl':      {'en': 'Heater Baud Rate',      'zh': '加热器波特率'},
    'heater_slave_lbl':     {'en': 'Slave ID',              'zh': '从机ID'},
    'heater_reg_sp_lbl':    {'en': 'Setpoint Register',     'zh': '设定点寄存器'},
    'heater_reg_act_lbl':   {'en': 'Actual Power Register', 'zh': '实际功率寄存器'},
    'heater_tol_lbl':       {'en': 'Watts Tolerance',       'zh': '功率容差'},
    'heater_max_lbl':       {'en': 'Max Watts (fixed)',      'zh': '最大功率 (固定)'},
    'heater_display_lbl':   {'en': 'Display Mode',          'zh': '显示模式'},
    'display_percent':      {'en': 'Percentage',             'zh': '百分比'},
    'display_watts':        {'en': 'Watts',                  'zh': '瓦特'},
    'display_both':         {'en': 'Both',                   'zh': '两者'},

    # ── Settings tab — response test fields ───────────────────────────────────
    'step_start_lbl':       {'en': 'Step Start (W)',             'zh': '阶段起始 (W)'},
    'step_end_lbl':         {'en': 'Step End (W)',               'zh': '阶段结束 (W)'},
    'step_size_lbl':        {'en': 'Step Size (W)',              'zh': '阶段大小 (W)'},
    'dwell_time_lbl':       {'en': 'Dwell Time (min)',           'zh': '停留时间 (分钟)'},
    'step_dur_lbl':         {'en': 'Stage Duration (min)',       'zh': '阶段持续时间 (分钟)'},
    'ss_window_lbl':        {'en': 'Steady State Window (sec)',  'zh': '稳态窗口 (秒)'},
    'ss_tolerance_lbl':     {'en': 'Steady State Tolerance (°C)','zh': '稳态容差 (°C)'},
    'thermal_threshold_lbl':{'en': 'Response Threshold (°C)',    'zh': '响应阈值 (°C)'},
    'thermal_samples_lbl':  {'en': 'Min Samples',                'zh': '最小样本数'},
    'thermal_sigma_lbl':    {'en': 'Sigma Multiplier',           'zh': 'Sigma乘数'},

    # ── Settings tab — display fields ─────────────────────────────────────────
    'theme_lbl':            {'en': 'Display Theme',     'zh': '显示主题'},
    'theme_light':          {'en': 'Light',             'zh': '浅色'},
    'theme_dark':           {'en': 'Dark',              'zh': '深色'},
    'language_lbl':         {'en': 'Language',          'zh': '语言'},

    # ── Settings tab — buttons ────────────────────────────────────────────────
    'btn_apply':            {'en': 'APPLY',             'zh': '应用'},
    'btn_reset':            {'en': 'RESET TO DEFAULTS', 'zh': '恢复默认'},
    'applied_ok':           {'en': '✓ Settings applied','zh': '✓ 设置已应用'},
    'restart_note':         {'en': 'Note: Port changes take effect on next connection',
                             'zh': '注意：端口更改在下次连接时生效'},

    # ── Heater tab ────────────────────────────────────────────────────────────
    'heater_setpoint':      {'en': 'HEATER SETPOINT',       'zh': '加热器设定值'},
    'heater_actual':        {'en': 'ACTUAL POWER',          'zh': '实际功率'},
    'heater_graph':         {'en': 'TEMPERATURE TREND (LAST 10 MIN)', 'zh': '温度趋势 (最近10分钟)'},
    'heater_modbus_log':    {'en': 'MODBUS LOG',            'zh': 'Modbus日志'},
    'btn_heater_on':        {'en': 'HEATER ON',             'zh': '加热器开'},
    'btn_heater_off':       {'en': 'HEATER OFF',            'zh': '加热器关'},

    # ── Response test tab ─────────────────────────────────────────────────────
    'resp_status':          {'en': 'TEST STATUS',           'zh': '测试状态'},
    'resp_stage':           {'en': 'CURRENT STAGE',         'zh': '当前阶段'},
    'resp_graph':           {'en': 'TEMPERATURE vs TIME',   'zh': '温度 vs 时间'},
    'resp_summary':         {'en': 'RESPONSE TIME vs STAGE','zh': '响应时间 vs 阶段'},
    'btn_resp_start':       {'en': '▶  START RESPONSE TEST','zh': '▶  开始响应测试'},
    'btn_resp_stop':        {'en': '■  ABORT',              'zh': '■  中止'},

    # ── Emergency stop ────────────────────────────────────────────────────────
    'estop_btn':            {'en': '⚠ EMERGENCY\nSTOP',     'zh': '⚠ 紧急\n停止'},
    'estop_title':          {'en': 'Emergency Stop',         'zh': '紧急停止'},
    'estop_msg':            {'en': 'Are you sure? This will immediately cut heater power and stop all active tests.',
                             'zh': '确认吗？这将立即切断加热器电源并停止所有活动测试。'},
}


def tr(key: str) -> str:
    """Return translated string for current language. Falls back to English."""
    lang = settings.get('language', 'en')
    if lang not in ('en', 'zh'):
        lang = 'en'
    entry = STRINGS.get(key, {})
    return entry.get(lang, entry.get('en', key))
