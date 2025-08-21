import time
import queue
from threading import Thread

from hal import hal_lcd as LCD
from hal import hal_keypad as keypad

shared_keypad_queue = queue.Queue()

def key_pressed(key):
    shared_keypad_queue.put(key)

idle_menu = [
    ["1.Start/Stop Eng", "2.Lock/Unlock"],
    ["3.Check Sensors", "4.Init Mobile Conn"],
    ["5.Low Power Mode", "6.Power Off"]
]

def show_idle_menu(lcd, page):
    lcd.lcd_clear()
    lcd.lcd_display_string(idle_menu[page][0], 1)
    lcd.lcd_display_string(idle_menu[page][1], 2)

def simulate_mobile_app_connect(lcd):
    lcd.lcd_clear()
    lcd.lcd_display_string("Connecting...", 1)
    time.sleep(1)

    correct_username = "12345"
    correct_password = "12345"
    entered_username = "12345"
    entered_password = "12345"

    if entered_username == correct_username and entered_password == correct_password:
        lcd.lcd_clear()
        lcd.lcd_display_string("Connected!", 1)
        time.sleep(2)

        lcd.lcd_clear()
        lcd.lcd_display_string("1.Lock/Unlock", 1)
        lcd.lcd_display_string("2.Climate Ctrl", 2)
        time.sleep(2)

        lcd.lcd_clear()
        lcd.lcd_display_string("3.View Status", 1)
        lcd.lcd_display_string("4.Manage User", 2)
        time.sleep(2)

        lcd.lcd_clear()
        lcd.lcd_display_string("Mobile Access:", 1)
        lcd.lcd_display_string("Ready", 2)
        time.sleep(2)
    else:
        lcd.lcd_clear()
        lcd.lcd_display_string("Auth Failed", 1)
        time.sleep(2)

def idle_menu_loop(lcd):
    current_page = 0
    show_idle_menu(lcd, current_page)

    while True:
        key = shared_keypad_queue.get()

        if key == '*':
            current_page = (current_page - 1) % 3
            show_idle_menu(lcd, current_page)
        elif key == '#':
            current_page = (current_page + 1) % 3
            show_idle_menu(lcd, current_page)
        elif key == '4' and current_page == 1:
            simulate_mobile_app_connect(lcd)
            show_idle_menu(lcd, current_page)
        elif key in ['1', '2', '3', '5', '6']:
            lcd.lcd_clear()
            lcd.lcd_display_string("Selected " + key, 1)
            time.sleep(2)
            show_idle_menu(lcd, current_page)
        elif key in ['A', 'B', 'C', 'D']:
            break
