# check_sensors.py
# Read & display environmental data on the LCD (F1 idle menu option 3).
# Uses shared state from g.py and HALs for LED, ADC (MCP3008), DHT11, and a moisture sensor.

import time
from typing import Optional, Tuple

import g as g # shared: lcd, and where we store thresholds & last readings
from hal import hal_led as led
from hal import hal_adc as adc
from hal import hal_temp_humidity_sensor as temp_humid_sensor
from hal import hal_moisture_sensor as moisture_sensor

# ---------- defaults / constants ----------
DFLT_DARK_THRESHOLD = 500   # MCP3008 scale: 0..1023 (tune to your LDR divider)
DFLT_LIGHT_CHANNEL  = 0     # MCP3008 channel for the LDR
LED_INDEX_LIGHT     = 0     # HAL ignores index; kept for readability
LED_INDEX_RAIN      = 1     # ditto

# ---------- init ----------
def init(dark_threshold: int = DFLT_DARK_THRESHOLD, light_channel: int = DFLT_LIGHT_CHANNEL) -> None:
    """
    One-time hardware init + shared-state bootstrap.
    Stores calibration & last-read values into g.*
    """
    # Init HALs (idempotent in your setup)
    led.init()
    adc.init()
    temp_humid_sensor.init()
    moisture_sensor.init()

    # Shared config in g
    setattr(g, "sensors_dark_threshold", int(dark_threshold))
    setattr(g, "sensors_light_channel", int(light_channel))

    # Last reading caches in g (for other modules to reuse if desired)
    for name, default in (
        ("last_temp",  None),
        ("last_humid", None),
        ("last_light", None),
        ("last_rain",  None),  # bool: True=raining, False=not raining, None=unknown
    ):
        if not hasattr(g, name):
            setattr(g, name, default)

# ---------- low-level reads ----------
def read_light_level() -> int:
    """Read ambient light from ADC channel set in g.sensors_light_channel. Returns 0..1023, or -1 on error."""
    ch = int(getattr(g, "sensors_light_channel", DFLT_LIGHT_CHANNEL))
    try:
        val = int(adc.get_adc_value(ch))
    except Exception:
        val = -1
    g.last_light = val
    return val

def read_temp_humidity() -> Tuple[Optional[float], Optional[float]]:
    """
    Read temperature & humidity from DHT11.
    Returns (temp_c, humid_pct) as floats, or (None, None) if invalid.
    """
    try:
        temp, humid = temp_humid_sensor.read_temp_humidity()  # [temp, humid] or [-100,-100]
        if temp == -100 or humid == -100:
            temp = humid = None
    except Exception:
        temp = humid = None
    g.last_temp, g.last_humid = temp, humid
    return temp, humid

def read_rain_status() -> Optional[bool]:
    """
    Read moisture sensor to infer 'raining'.
    Returns True/False, or None on error.
    """
    try:
        raining = bool(moisture_sensor.read_sensor())
    except Exception:
        raining = None
    g.last_rain = raining
    return raining

# ---------- UI helpers ----------
def _lcd_lines(line1: str = "", line2: str = "", hold_s: float = 0.0) -> None:
    """Draw up to two lines on the shared LCD with an optional hold."""
    try:
        g.lcd.lcd_clear()
        if line1:
            g.lcd.lcd_display_string(str(line1), 1)
        if line2:
            g.lcd.lcd_display_string(str(line2), 2)
    except Exception:
        # If LCD not available, just skip drawing
        pass
    if hold_s > 0:
        time.sleep(hold_s)

# ---------- screen flows (single-shot; no loops) ----------
def show_environmental_data(duration_s: float = 2.0) -> None:
    """
    Screen 1: Temperature/Humidity + Light level (or N/A if not available).
    """
    temp, humid = read_temp_humidity()
    light_val = read_light_level()

    if temp is None or humid is None:
        _lcd_lines(
            line1=f"Amb:N/A  L:{light_val if light_val>=0 else 'N/A'}",
            line2="Humid:N/A",
            hold_s=duration_s,
        )
    else:
        _lcd_lines(
            line1=f"Amb:{temp:.1f}C L:{light_val if light_val>=0 else 'N/A'}",
            line2=f"Humid:{humid:.1f}%",
            hold_s=duration_s,
        )

def update_lighting(duration_s: float = 2.0) -> None:
    """
    Screen 2: Set LED ON if it's 'dark' and show the decision.
    Uses g.sensors_dark_threshold.
    """
    light_val = read_light_level()
    thr = int(getattr(g, "sensors_dark_threshold", DFLT_DARK_THRESHOLD))

    # Decide & drive LED (note: HAL ignores the index arg)
    is_dark = (light_val >= 0 and light_val > thr)
    try:
        led.set_output(LED_INDEX_LIGHT, 1 if is_dark else 0)
    except Exception:
        pass

    _lcd_lines(
        line1=("Light ON  - Dark" if is_dark else "Light OFF - Bright"),
        line2=(f"Level: {light_val}" if light_val >= 0 else "Level: N/A"),
        hold_s=duration_s,
    )

def update_rain_status(duration_s: float = 2.0) -> None:
    """
    Screen 3: Read moisture sensor; show rain status.
    """
    raining = read_rain_status()
    
    if raining is True:
        _lcd_lines("Rain Detected", "Wipers ON", hold_s=duration_s)
    elif raining is False:
        _lcd_lines("No Rain", "Wipers OFF", hold_s=duration_s)
    else:
        _lcd_lines("Rain: N/A", "", hold_s=duration_s)

def display_all(duration_s: float = 2.0) -> None:
    """
    Convenience: show all three screens in sequence once.
    Intended to be called from F1 idle menu option 3.
    """
    show_environmental_data(duration_s)
    update_lighting(duration_s)
    update_rain_status(duration_s)

# ---------- optional cleanup ----------
def cleanup() -> None:
    """Optional: turn off LED and clear LCD on exit."""
    try:
        led.set_output(LED_INDEX_LIGHT, 0)
    except Exception:
        pass
    try:
        g.lcd.lcd_clear()
    except Exception:
        pass
