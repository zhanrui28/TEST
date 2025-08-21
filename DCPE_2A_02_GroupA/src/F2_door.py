# lock_unlock_door.py
# Servo-driven door lock for Raspberry Pi.
# Integrates with F1_menu; shares state via g.py.
#
# Public API:
#   init(lock_angle=0, unlock_angle=90, default_state="locked")
#   lock()
#   unlock()
#   toggle_lock()
#   is_locked()
#   set_angles(lock_angle, unlock_angle)

import time
from hal import hal_servo
import g as g  # expects g.lcd to be present (from your existing g.py)

# ---------- helpers ----------
def _clamp_angle(a):
    try:
        a = float(a)
    except Exception:
        a = 0.0
    return max(0.0, min(180.0, a))

def _apply_servo(angle=None, settle_s=0.2):
    """Send the servo to the desired angle."""
    if angle is None:
        angle = g.lock_angle if g.locked else g.unlock_angle
    angle = _clamp_angle(angle)
    try:
        hal_servo.set_servo_position(angle)
    except Exception as e:
        # Keep UI responsive even if servo errors
        _lcd_lines(("Servo error", str(e)))
    time.sleep(settle_s)

def _lcd_lines(lines, hold_s=1.0):
    """Safe LCD drawing using shared g.lcd; lines is tuple/list of up to 2 strings."""
    try:
        g.lcd.lcd_clear()
        if len(lines) > 0 and lines[0]:
            g.lcd.lcd_display_string(str(lines[0]), 1)
        if len(lines) > 1 and lines[1]:
            g.lcd.lcd_display_string(str(lines[1]), 2)
    except Exception:
        # If LCD not available, just skip
        pass
    if hold_s > 0:
        time.sleep(hold_s)

# ---------- public API ----------
def init(lock_angle=0, unlock_angle=90, default_state="locked"):
    """
    Initialize the servo lock.
      - lock_angle / unlock_angle: degrees in [0..180]
      - default_state: "locked" or "unlocked"
    Stores angles and state in g.*, and moves servo to default state.
    """
    hal_servo.init()

    # Create shared fields in g if missing
    if not hasattr(g, "locked"):
        g.locked = True
    if not hasattr(g, "lock_angle"):
        g.lock_angle = 0.0
    if not hasattr(g, "unlock_angle"):
        g.unlock_angle = 90.0

    g.lock_angle = _clamp_angle(lock_angle)
    g.unlock_angle = _clamp_angle(unlock_angle)
    g.locked = (str(default_state).lower() == "locked")

    # Move to default state
    _apply_servo()
    _lcd_lines(("Door " + ("Locked" if g.locked else "Unlocked"), ""), hold_s=0.6)

def lock(show_ui=True):
    """Lock the door (move servo to lock angle)."""
    g.locked = True
    _apply_servo()
    if show_ui:
        _lcd_lines(("Door Locked", ""), hold_s=0.8)

def unlock(show_ui=True):
    """Unlock the door (move servo to unlock angle)."""
    g.locked = False
    _apply_servo()
    if show_ui:
        _lcd_lines(("Door Unlocked", ""), hold_s=0.8)

def toggle_lock(show_ui=True):
    """Toggle the door lock state."""
    if is_locked():
        unlock(show_ui=show_ui)
    else:
        lock(show_ui=show_ui)

def is_locked():
    """Return True if the door is currently locked."""
    return bool(getattr(g, "locked", True))

def set_angles(lock_angle, unlock_angle, show_ui=True):
    """
    Update servo angles and re-apply current state.
    Useful for quick on-device calibration.
    """
    g.lock_angle = _clamp_angle(lock_angle)
    g.unlock_angle = _clamp_angle(unlock_angle)
    _apply_servo()
    if show_ui:
        _lcd_lines(("Angles set", f"L:{int(g.lock_angle)} U:{int(g.unlock_angle)}"), hold_s=1.0)
