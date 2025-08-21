# integrated_F1_F3_4.py
# Orchestrates keypad init, engine init, alarm init, boot flow, and calls F1_menu.

import time
import threading
import queue

from hal import hal_keypad as keypad

import g as g # shared: lcd, shared_keypad_queue
import F1_menu as F1

from F3_4_start_stop_engine import (
    init as engine_init,
    ensure_switch_off_at_launch,
    enforce_switch_safety,
    stop_engine,
    is_engine_running,
)

import F9_Intruder_detect as alarm

# ---------- Keypad ----------
def key_pressed(k):
    """HAL keypad callback — push key into the shared queue."""
    k = str(k)
    try:
        g.shared_keypad_queue.put_nowait(k)
    except queue.Full:
        try:
            g.shared_keypad_queue.get_nowait()
        except queue.Empty:
            pass
        g.shared_keypad_queue.put_nowait(k)

def _scan_keys():
    """Blocking scanner that invokes the callback; run in a daemon thread."""
    keypad.get_key()

# ---------- Main ----------
def main():
    # Engine init — set allowed_uids to restrict, or None to accept any
    engine_init(require_rfid_each_start=True, allowed_uids=None)

    # Alarm init — will use g.rfid_allowed_uids if present
    try:
        alarm.init(allowed_uids=g.rfid_allowed_uids)
    except Exception:
        alarm.init(allowed_uids=None)

    # Keypad init and scanner thread
    keypad.init(key_pressed)
    threading.Thread(target=_scan_keys, daemon=True).start()

    # Require slide switch OFF before any UI
    ensure_switch_off_at_launch()

    # Boot text
    g.lcd.lcd_clear()
    g.lcd.lcd_display_string("System Ready", 1)
    g.lcd.lcd_display_string("Press 1 to Start", 2)
    time.sleep(1.0)

    # Show main menu and wait for input
    F1.show_main_menu()

    try:
        while True:
            # Keep enforcing safety and watching alarm even on main menu
            enforce_switch_safety()
            alarm.monitor_ir_and_trigger()

            if getattr(g, "alarm_active", False):
                # Consume stray keys while alarm modal owns control
                try:
                    while True:
                        g.shared_keypad_queue.get_nowait()
                except queue.Empty:
                    pass
                time.sleep(0.05)
                continue

            try:
                key = g.shared_keypad_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if key == '1':
                F1.idle_menu_loop()
                F1.show_main_menu()

            elif key == '2':
                # Optional: allow quick Lock/Unlock from main menu
                import F2_door as door
                door.toggle_lock()
                time.sleep(0.4)
                F1.show_main_menu()

    except KeyboardInterrupt:
        try:
            if is_engine_running():
                stop_engine()
        finally:
            g.lcd.lcd_clear()
            print("Exiting.")

if __name__ == "__main__":
    main()
