# check_sensors.py
# Read & display environmental data on the LCD (F1 idle menu option 3).
# Uses shared state from g.py and HALs for LED, ADC (MCP3008), DHT11, and a moisture sensor.
#
# New in this version:
#   - "invert dark" support: treat DARK as (light_val < threshold) when invert is True
#   - Better LCD debug for the light decision (shows raw level, threshold, and Dark/Bright)
#   - Simple setters for threshold/channel/invert, and a quick calibration helper

import time
from typing import Optional, Tuple

import g  # shared: lcd + config fields
from hal import hal_led as led
from hal import hal_adc as adc
from hal import hal_temp_humidity_sensor as temp_humid_sensor
from hal import hal_moisture_sensor as moisture_sensor

# ---------- defaults / constants ----------
DFLT_DARK_THRESHOLD = 500    # MCP3008 scale: 0..1023
DFLT_LIGHT_CHANNEL  = 0      # MCP3008 channel for the LDR
DFLT_INVERT_DARK    = False  # If True, DARK means value < threshold
LED_INDEX_LIGHT     = 0      # HAL ignores index; kept for readability

# ---------- init ----------
def init(
    dark_threshold: int = DFLT_DARK_THRESHOLD,
    light_channel: int = DFLT_LIGHT_CHANNEL,
    invert_dark: bool = DFLT_INVERT_DARK,
) -> None:
    """
    One-time hardware init + shared-state bootstrap.
    Stores calibration & last-read values into g.*
    """
    led.init()
    adc.init()
    temp_humid_sensor.init()
    moisture_sensor.init()

    setattr(g, "sensors_dark_threshold", int(dark_threshold))
    setattr(g, "sensors_light_channel", int(light_channel))
    setattr(g, "sensors_dark_invert", bool(invert_dark))

    # Last reading caches in g (for other modules to reuse if desired)
    for name, default in (
        ("last_temp",  None),
        ("last_humid", None),
        ("last_light", None),
        ("last_rain",  None),  # bool: True=raining, False=not raining, None=unknown
    ):
        if not hasattr(g, name):
            setattr(g, name, default)

# ---------- config setters (optional utilities) ----------
def set_dark_threshold(th: int) -> None:
    setattr(g, "sensors_dark_threshold", int(th))

def set_light_channel(ch: int) -> None:
    setattr(g, "sensors_light_channel", int(ch))

def set_invert_dark(flag: bool) -> None:
    setattr(g, "sensors_dark_invert", bool(flag))

def quick_calibrate_dark_threshold(samples: int = 10, margin: int = 50) -> int:
    """
    Quickly calibrate threshold around current ambient light.
    Returns the threshold chosen and stores it in g.sensors_dark_threshold.
    """
    vals = []
    for _ in range(max(1, samples)):
        v = read_light_level()
        if v >= 0:
            vals.append(v)
        time.sleep(0.02)
    if not vals:
        return int(getattr(g, "sensors_dark_threshold", DFLT_DARK_THRESHOLD))
    avg = sum(vals) // len(vals)
    th = max(0, min(1023, avg + (margin if not getattr(g, "sensors_dark_invert", False) else -margin)))
    set_dark_threshold(th)
    return th

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
    Read moisture sensor; True/False or None on error.
    """
    try:
        raining = bool(moisture_sensor.read_sensor())
    except Exception:
        raining = None
    g.last_rain = raining
    return raining

# ---------- light decision ----------
def _is_dark(light_val: int, thr: int, invert: bool) -> bool:
    """
    Decide 'dark' based on current value, threshold, and invert flag.
    If invert is False: dark when light_val > thr (typical if LDR up = Vout increases in dark)
    If invert is True : dark when light_val < thr (typical if LDR down = Vout decreases in dark)
    """
    if light_val < 0:
        return False
    return (light_val < thr) if invert else (light_val > thr)

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
    Screen 2: Determine darkness and drive LED.
    Uses g.sensors_dark_threshold and g.sensors_dark_invert.
    """
    light_val = read_light_level()
    thr = int(getattr(g, "sensors_dark_threshold", DFLT_DARK_THRESHOLD))
    invert = bool(getattr(g, "sensors_dark_invert", DFLT_INVERT_DARK))

    is_dark = _is_dark(light_val, thr, invert)

    # Drive LED only on valid reading
    if light_val >= 0:
        try:
            led.set_output(LED_INDEX_LIGHT, 1 if is_dark else 0)
        except Exception:
            pass

    # Helpful debug on LCD: show raw level, threshold, and decision
    # e.g. "Lvl: 432 Th:500" and "Dark" / "Bright"
    _lcd_lines(
        line1=(f"Lvl:{light_val if light_val>=0 else 'N/A'} Th:{thr}"),
        line2=("Dark" if is_dark else "Bright") + (" (inv)" if invert else ""),
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