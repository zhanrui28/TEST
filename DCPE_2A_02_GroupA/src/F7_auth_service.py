# rfid_access.py
# Centralized RFID access control for the project.
# Only UIDs in the allowed list are accepted by engine start & alarm clear.

import time
from typing import Iterable, Optional, Tuple

import g as g
from hal import hal_rfid_reader
from hal import hal_lcd as hal_lcd

# Reader handle
_reader = None

# Direct LCD fallback (if someone calls before g.lcd exists)
_LCD = None

# ------------- helpers -------------
def _ensure_reader():
    global _reader
    if _reader is None:
        _reader = hal_rfid_reader.init()  # returns SimpleMFRC522

def _ensure_lcd():
    global _LCD
    if _LCD is None:
        try:
            _LCD = hal_lcd.lcd()
        except Exception:
            _LCD = None

def _lcd(line1="", line2="", hold_s: float = 0.0):
    # Prefer shared LCD in g (if present), else direct fallback
    lcd = getattr(g, "lcd", None)
    if lcd is None:
        _ensure_lcd()
        lcd = _LCD
    if lcd is None:
        if hold_s > 0:
            time.sleep(hold_s)
        return
    try:
        lcd.lcd_clear()
        if line1:
            lcd.lcd_display_string(str(line1), 1)
        if line2:
            lcd.lcd_display_string(str(line2), 2)
    except Exception:
        pass
    if hold_s > 0:
        time.sleep(hold_s)

def _normalize_uids(uids: Iterable) -> set:
    s = set()
    for u in (uids or []):
        try:
            s.add(int(u))
        except Exception:
            s.add(str(u))
    return s

# ------------- public API -------------
def init(allowed_uids: Optional[Iterable] = None) -> None:
    """
    Initialize reader and allowed UID set.
    If allowed_uids is None, use g.rfid_allowed_uids; if that is also None,
    default to the three project tags provided.
    """
    _ensure_reader()

    if allowed_uids is None:
        # Use g.rfid_allowed_uids if set, else default to your three tags
        default_list = [966206689390, 470912245720, 988692462534]
        allowed_uids = getattr(g, "rfid_allowed_uids", default_list) or default_list

    set_allowed(allowed_uids)

def set_allowed(uids: Iterable) -> None:
    """Replace the allowed UID set (updates g.rfid_allowed_uids)."""
    s = _normalize_uids(uids)
    # store both int & str forms for robust matching
    both = set()
    for u in s:
        try:
            both.add(int(u))
        except Exception:
            pass
        both.add(str(u))
    g.rfid_allowed_uids = list(both)

def is_allowed(uid) -> bool:
    """Check a UID against the current allowed set."""
    allowed = getattr(g, "rfid_allowed_uids", None) or []
    return (uid in allowed) or (str(uid) in allowed)

def read_id_blocking():
    """Blocking read of the next RFID tap; returns the UID (int)."""
    _ensure_reader()
    return _reader.read_id()

def authorized_tap_blocking(
    prompt_line1: str = "Tap Authorized RFID",
    prompt_line2: str = "",
    denied_hold_s: float = 0.8,
) -> Tuple[bool, Optional[int]]:
    """
    Keep prompting until an allowed RFID is tapped.
    Returns (True, uid) on success. On unexpected reader error, returns (False, None).
    """
    _ensure_reader()

    while True:
        _lcd(prompt_line1, prompt_line2, hold_s=0.0)
        try:
            uid = _reader.read_id()  # BLOCKS until a card is tapped
        except Exception:
            _lcd("RFID read error", "Try again", denied_hold_s)
            return (False, None)

        if is_allowed(uid):
            _lcd("Access Granted", "", 0.5)
            return (True, uid)

        _lcd("Access denied", f"UID:{uid}", denied_hold_s)
        # loop to prompt again
