# F1_menu.py
# Owns menu UI + idle loop. Integrates:
#   - F2: Lock/Unlock Door (servo)
#   - F3/F4: Start/Stop Engine (RFID -> wait for slide switch ON -> start)
#   - Option 3: Check Sensors (temp/humid/light/rain)
#   - Alarm monitor: blocks UI if alarm modal is triggered

import time
import queue

import g  as g# shared: lcd, shared_keypad_queue, current_page, idle_menu, PAGES, etc.

# Engine controls (F3/F4)
from F3_4_start_stop_engine import (
    toggle_engine,
    enforce_switch_safety,
    stop_engine,
    is_engine_running,
)

# F2: Door lock/unlock (servo)
import F2_door as door

# F3: Sensors
import F5_environment_monitor as sensors

# Alarm system (modal; blocks everything until RFID clears)
import F9_Intruder_detect as alarm

# ---------- Initialize modules that render to LCD / use shared config ----------
door.init(
    lock_angle=g.lock_angle,
    unlock_angle=g.unlock_angle,
    default_state=("locked" if g.locked else "unlocked"),
)

sensors.init(
    dark_threshold=g.sensors_dark_threshold,
    light_channel=g.sensors_light_channel,
)

# Alarm init typically done in integrator too; harmless here
try:
    alarm.init(allowed_uids=g.rfid_allowed_uids)
except Exception:
    alarm.init(allowed_uids=None)

# ---------- UI helpers ----------
def show_main_menu():
    g.lcd.lcd_clear()
    g.lcd.lcd_display_string("1. Initialize", 1)
    g.lcd.lcd_display_string("2. Lock/Unlock", 2)

def show_idle_menu():
    g.lcd.lcd_clear()
    top, bottom = g.idle_menu[g.current_page]
    g.lcd.lcd_display_string(top, 1)
    g.lcd.lcd_display_string(bottom, 2)

# ---------- Idle menu loop ----------
def idle_menu_loop():
    show_idle_menu()

    while True:
        # 1) Safety: stop engine if slide switch flips OFF
        if enforce_switch_safety()==False:
            show_idle_menu()

        # 2) Alarm monitoring: if door locked and IR changes, this will
        #    ENTER a MODAL loop and only return after RFID clears the alarm.
        alarm.monitor_ir_and_trigger()

        # If alarm is active, drain keys & wait
        if getattr(g, "alarm_active", False):
            try:
                while True:
                    g.shared_keypad_queue.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.05)
            continue  # modal alarm still owns control
        
        if getattr(g, "return_to_main_menu", False):
            g.return_to_main_menu = False
            return
        
        # 3) UI input
        try:
            key = g.shared_keypad_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if key == '*':
            g.current_page = (g.current_page - 1) % g.PAGES
            show_idle_menu()

        elif key == '#':
            g.current_page = (g.current_page + 1) % g.PAGES
            show_idle_menu()

        elif key == '1' and g.current_page == 0:
            # F3/F4: Start/Stop Engine
            toggle_engine()
            time.sleep(1.0)  # allow engine status to show
            show_idle_menu()

        elif key == '2' and g.current_page == 0:
            # F2: Lock/Unlock Door (servo) — this also updates g.locked
            door.toggle_lock()
            time.sleep(0.2)
            show_idle_menu()

        elif key == '3' and g.current_page == 1:
            # Check Sensors (3 screens ~6s total)
            sensors.display_all(duration_s=2.0)
            show_idle_menu()

        elif key == '4' and g.current_page == 1:
            g.lcd.lcd_clear()
            g.lcd.lcd_display_string("Init Mobile Conn", 1)
            time.sleep(1.2)
            show_idle_menu()

        elif key == '5' and g.current_page == 2:
            g.lcd.lcd_clear()
            g.lcd.lcd_display_string("Low Power Mode", 1)
            time.sleep(1.0)
            show_idle_menu()

        elif key == '6' and g.current_page == 2:
            g.lcd.lcd_clear()
            g.lcd.lcd_display_string("Powering Off", 1)
            if is_engine_running():
                stop_engine()
                time.sleep(0.5)
            g.lcd.lcd_clear()
            return  # exit back to main menu
