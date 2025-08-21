# g.py
# Shared state for integrated_F1_F3_4, F1_menu, lock_unlock_door, check_sensors, alarm_system.
# IMPORTANT: No blocking calls at import.

import queue

# ----------------------------
# Keypad event queue
# ----------------------------
shared_keypad_queue = queue.Queue(maxsize=64)

# ----------------------------
# LCD (shared). Safe no-op fallback if HAL isn't available.
# ----------------------------
try:
    from hal import hal_lcd as LCD
    lcd = LCD.lcd()
except Exception:
    class _NoOpLCD:
        def lcd_clear(self): pass
        def lcd_display_string(self, *args, **kwargs): pass
    lcd = _NoOpLCD()


# >>> Set the project’s allowed RFID tags here <<<
rfid_allowed_uids = [966206689390, 470912245720, 988692462534]
# ----------------------------
# Menu state (shared)
# ----------------------------
current_page = 0
idle_menu = [
    ["1. Start/Stop Engine", "2. Lock/Unlock Door"],
    ["3. Check Sensors",     "4. Initialise Mobile Conn"],
    ["5. Low power mode",    "6. Power off"]
]
PAGES = len(idle_menu)

# ----------------------------
# Door lock shared defaults (used by lock_unlock_door)
# ----------------------------
locked = True        # True = locked/closed door, False = unlocked/open
lock_angle = 0.0     # degrees [0..180]
unlock_angle = 90.0  # degrees [0..180]

# ----------------------------
# Sensors shared config + last readings (used by check_sensors)
# ----------------------------
sensors_dark_threshold = 500   # MCP3008: 0..1023
sensors_light_channel  = 0     # MCP3008 channel (0..7)
last_temp  = None              # float or None
last_humid = None              # float or None
last_light = None              # int   or None
last_rain  = None              # bool  or None (True=raining)

# ----------------------------
# Alarm system shared flags (used by alarm_system)
# ----------------------------
alarm_active  = False          # True when alarm modal is running
ir_last_state = None           # last IR boolean state (True/False)
rfid_allowed_uids = None       # e.g., ["12345", 67890]; None = accept any
alarm_debug = False            # set True to print alarm debug
return_to_main_menu = False

# ----------------------------
# Misc flags (optional)
# ----------------------------
loop_indicate = False
