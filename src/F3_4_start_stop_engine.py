# f3_f4_engine.py
# Engine Start/Stop (F3/F4) for Raspberry Pi using your HALs.
# Start order: RFID -> wait for slide switch ON -> start motor
# At launch: provide helper to ensure slide switch is OFF before UI begins.

import time
from hal import hal_dc_motor
from hal import hal_rfid_reader
from hal import hal_lcd
from hal import hal_input_switch
import g as g

# Module-level state
_engine_running = False
_require_rfid_each_start = True
_allowed_uids = None

# HAL objects (set in init())
rfid = None
lcd = None

def init(require_rfid_each_start=True, allowed_uids=None):
    """
    Must be called once at program startup.
      - require_rfid_each_start: if True, user must tap a card on every Start.
      - allowed_uids: iterable of allowed UIDs (ints or strings). If None, any UID is accepted.
    """
    global rfid, lcd, _require_rfid_each_start, _allowed_uids
    hal_dc_motor.init()
    hal_input_switch.init()
    rfid = hal_rfid_reader.init()   # SimpleMFRC522
    lcd = hal_lcd.lcd()
    _require_rfid_each_start = bool(require_rfid_each_start)
    _allowed_uids = set(allowed_uids) if allowed_uids else None

def is_engine_running():
    return _engine_running

def read_slide_switch():
    """Return 1 if ON, 0 if OFF."""
    return hal_input_switch.read_slide_switch()

def ensure_switch_off_at_launch():
    """
    Call once at program start. Prompts user to turn slide switch OFF first
    and waits until it is OFF before continuing.
    """
    if read_slide_switch() == 0:
        return
    lcd.lcd_clear()
    lcd.lcd_display_string("Turn slide switch", 1)
    lcd.lcd_display_string("OFF to begin", 2)
    while read_slide_switch() != 0:
        time.sleep(0.1)
    lcd.lcd_clear()
    lcd.lcd_display_string("OK: Switch OFF", 1)
    time.sleep(0.8)
    lcd.lcd_clear()

def _authenticate_rfid():
    """Blocks until a card is tapped; True if allowed (or open)."""
    if not _require_rfid_each_start:
        return True

    lcd.lcd_clear()
    lcd.lcd_display_string("Tap RFID Card", 1)
    uid = rfid.read_id()  # blocks until card tapped (int UID)

    if _allowed_uids is None or (uid in _allowed_uids) or (str(uid) in _allowed_uids):
        lcd.lcd_clear()
        lcd.lcd_display_string("Access Granted", 1)
        time.sleep(0.6)
        return True
    else:
        lcd.lcd_clear()
        lcd.lcd_display_string("Access denied", 1)
        time.sleep(0.9)
        return False

def _wait_for_switch_on():
    """
    Prompt and wait until slide switch is ON (1).
    If already ON, proceeds immediately.
    """
    if read_slide_switch() == 1:
        return
    lcd.lcd_clear()
    lcd.lcd_display_string("Turn slide switch", 1)
    lcd.lcd_display_string("ON to start", 2)
    while read_slide_switch() != 1:
        time.sleep(0.1)

def start_engine():
    """
    Start the motor (100% duty) if:
      - engine not already running
      - RFID passes
      - (then) slide switch becomes ON
    Returns True on success, False otherwise.
    """
    global _engine_running
    if _engine_running:
        return True

    # 1) RFID first
    if not _authenticate_rfid():
        return False

    # 2) Then wait for switch to be ON
    _wait_for_switch_on()

    # 3) Start motor
    hal_dc_motor.set_motor_speed(100)
    lcd.lcd_clear()
    lcd.lcd_display_string("Engine started", 1)
    lcd.lcd_display_string("Drive safely", 2)
    _engine_running = True
    return True

def stop_engine():
    """Stop the motor and update display. Always returns True."""
    global _engine_running
    if not _engine_running:
        return True

    hal_dc_motor.set_motor_speed(0)
    lcd.lcd_clear()
    lcd.lcd_display_string("Engine stopped", 1)
    time.sleep(1.0)
    _engine_running = False
    return True

def toggle_engine():
    """
    Convenience:
      - If running: stop immediately.
      - If stopped: RFID -> wait switch ON -> start.
    """
    return stop_engine() if _engine_running else start_engine()

def enforce_switch_safety():
    """
    Call this periodically from your UI loop.
    If the slide switch turns OFF while running, stop the engine.
    Returns False if it had to stop the engine, True otherwise.
    """
    if _engine_running and read_slide_switch() == 0:
        stop_engine()
        return False
    return True

def cleanup():
    """Optional: call on program exit."""
    try:
        hal_dc_motor.set_motor_speed(0)
    except Exception:
        pass
    try:
        lcd.lcd_clear()
    except Exception:
        pass