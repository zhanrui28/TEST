# alarm_system.py
# Modal alarm: triggers on a specific IR edge while the door is CLOSED (g.locked == True),
# sounds buzzer continuously, and can ONLY be cleared via RFID.
#
# Public API:
#   init(allowed_uids=None)
#   monitor_ir_and_trigger()
#   run_alarm_modal()
#
# HALs used:
#   IR     : hal_ir_sensor.get_ir_sensor_state() -> bool (True = object detected)
#   Buzzer : hal_buzzer.turn_on() / turn_off()
#   RFID   : hal_rfid_reader.init().read_id()
#   LCD    : (via g.lcd_queue if present) or direct hal_lcd fallback

import time
import queue

import g as g
import F1_menu as F1
from hal import hal_ir_sensor as ir_sensor
from hal import hal_buzzer as buzzer
from hal import hal_rfid_reader as rfid_reader
from hal import hal_lcd as hal_lcd  # fallback if g.lcd_queue not present

_rfid = None
_allowed_uids = None

# Fallback LCD handle (only used if g.lcd_queue isn't available)
_LCD = None

def init(allowed_uids=None):
    """One-time init. Pass allow-list; None = accept any UID."""
    global _rfid, _allowed_uids, _LCD

    try:
        ir_sensor.init()
    except Exception:
        _dbg("IR init skipped/failed")

    try:
        buzzer.init()
    except Exception:
        _dbg("Buzzer init skipped/failed")

    try:
        _rfid = rfid_reader.init()   # SimpleMFRC522
    except Exception:
        _rfid = None
        _dbg("RFID init failed (alarm cannot be cleared without RFID)")

    # Prepare direct LCD fallback if no queue exists
    if not hasattr(g, "lcd_queue"):
        try:
            _LCD = hal_lcd.lcd()
        except Exception:
            _LCD = None

    # Defaults (only if missing)
    if not hasattr(g, "alarm_active"):
        g.alarm_active = False
    if not hasattr(g, "ir_last_state"):
        g.ir_last_state = _read_ir()  # seed baseline (may be None)
    if not hasattr(g, "alarm_debug"):
        g.alarm_debug = False
    # Default trigger = 'falling' so it works even if IR idles True
    if not hasattr(g, "alarm_trigger_edge"):
        g.alarm_trigger_edge = "falling"   # 'rising' | 'falling' | 'any'
    if not hasattr(g, "alarm_ir_hold_ms"):
        g.alarm_ir_hold_ms = 60            # debounce/confirm duration (ms)

    if allowed_uids is None and getattr(g, "rfid_allowed_uids", None) is not None:
        allowed_uids = g.rfid_allowed_uids
    _allowed_uids = set(allowed_uids) if allowed_uids else None

def _dbg(msg):
    if getattr(g, "alarm_debug", False):
        print("[ALARM]", msg)

# ---------------- LCD output helpers ----------------
def _lcd_enqueue(line1="", line2="", hold_s=0.0, clear=True):
    """
    Prefer sending to a central LCD queue if g.lcd_queue exists.
    Expected item format (keep simple & consistent with your display thread):
        {"line1": str, "line2": str, "hold_s": float, "clear": bool}
    """
    item = {"line1": str(line1) if line1 is not None else "",
            "line2": str(line2) if line2 is not None else "",
            "hold_s": float(hold_s) if hold_s else 0.0,
            "clear": bool(clear)}
    try:
        g.lcd_queue.put_nowait(item)
        return True
    except AttributeError:
        # No queue present
        return False
    except queue.Full:
        # Drop oldest and retry
        try:
            g.lcd_queue.get_nowait()
        except Exception:
            pass
        try:
            g.lcd_queue.put_nowait(item)
            return True
        except Exception:
            return False

def _lcd_direct(line1="", line2="", hold_s=0.0):
    """Fallback: write directly using hal_lcd if queue isn't available."""
    if _LCD is None:
        return
    try:
        _LCD.lcd_clear()
        if line1:
            _LCD.lcd_display_string(str(line1), 1)
        if line2:
            _LCD.lcd_display_string(str(line2), 2)
        if hold_s > 0:
            time.sleep(hold_s)
    except Exception:
        pass

def _lcd(line1="", line2="", hold_s=0.0):
    """Unified LCD API for this module (queue first, then direct fallback)."""
    if not _lcd_enqueue(line1, line2, hold_s, clear=True):
        _lcd_direct(line1, line2, hold_s)

# ---------------- Hardware helpers ----------------
def _buzz(on: bool):
    try:
        if on: buzzer.turn_on()
        else:  buzzer.turn_off()
    except Exception:
        _dbg("Buzzer control failed")

def _read_ir():
    """Return True/False from HAL, or None on error (True = object detected)."""
    try:
        return bool(ir_sensor.get_ir_sensor_state())
    except Exception:
        return None

def _edge_should_trigger(prev: bool, cur: bool) -> bool:
    """Return True iff transition prev->cur matches configured edge."""
    edge = str(getattr(g, "alarm_trigger_edge", "falling")).lower()
    if edge == "rising":
        return (prev is False) and (cur is True)
    if edge == "falling":
        return (prev is True) and (cur is False)
    # "any"
    return prev != cur

def _rfid_ok_blocking() -> bool:
    """Block until a card is tapped. Return True if allowed (or open mode)."""
    if _rfid is None:
        _lcd("RFID missing!", "Alarm locked", 1.0)
        return False

    _lcd("ALARM! Present", "RFID to clear", 0.1)
    try:
        uid = _rfid.read_id()  # BLOCKS until card tap
        _dbg(f"RFID UID={uid}")
    except Exception:
        _lcd("RFID read error", "Try again", 0.8)
        return False

    if _allowed_uids is None:
        return True
    if uid in _allowed_uids or str(uid) in _allowed_uids:
        return True

    _lcd("Access denied", f"UID:{uid}", 1.0)
    return False

# ---------------- Public API ----------------
def monitor_ir_and_trigger():
    """
    Call this frequently (e.g., each loop iteration).
    If door is closed (g.locked True) AND the configured edge occurs,
    trigger modal alarm.
    """
    if getattr(g, "alarm_active", False):
        return

    # Only armed when the door is closed/locked
    if not getattr(g, "locked", True):
        g.ir_last_state = _read_ir()  # update baseline while unlocked
        return

    cur = _read_ir()
    if cur is None:
        _dbg("IR read failed")
        return

    prev = g.ir_last_state
    if prev is None:
        g.ir_last_state = cur
        return

    # Trigger only on the configured edge (default: falling True->False)
    if _edge_should_trigger(prev, cur):
        hold_ms = int(getattr(g, "alarm_ir_hold_ms", 60))
        time.sleep(max(0, hold_ms) / 1000.0)
        confirm = _read_ir()
        if confirm is not None and confirm == cur and _edge_should_trigger(prev, confirm):
            _dbg(f"IR edge '{getattr(g,'alarm_trigger_edge','falling')}' confirmed: {prev} -> {cur}")
            run_alarm_modal()
            g.ir_last_state = cur
            return

    # No trigger; update baseline
    g.ir_last_state = cur

def run_alarm_modal():
    """Enter ALARM mode until a valid RFID clears it."""
    g.alarm_active = True
    _buzz(True)
    _lcd("!!! ALARM !!!", "RFID required", 0.2)

    try:
        while True:
            if _rfid_ok_blocking():
                break
            _buzz(True)  # keep asserted
            time.sleep(0.1)
    finally:
        _buzz(False)
        g.alarm_active = False
        _lcd("Alarm cleared", "", 0.8)
        _lcd()  # clear

        # Ask the UI to jump back to MAIN MENU (integrator will handle it)
        g.return_to_main_menu = True
