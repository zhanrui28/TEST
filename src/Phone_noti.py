# alarm_camera.py
from threading import Thread
from picamera2 import Picamera2, Preview

_picam2 = None
_preview_mode = Preview.QTGL  # change to Preview.DRM or Preview.NULL if headless

def setup_camera():
    """
    Start Picamera2 preview & stream. Idempotent (safe to call multiple times).
    Returns the Picamera2 instance.
    """
    global _picam2
    if _picam2 is not None:
        return _picam2

    cam = Picamera2()
    cfg = cam.create_still_configuration(
        main={"size": (1920, 1080)},
        lores={"size": (640, 480)},
        display="lores",
    )
    cam.configure(cfg)

    # Try preferred preview; fall back if not available (e.g., headless)
    try:
        cam.start_preview(_preview_mode)
    except Exception:
        try:
            cam.start_preview(Preview.DRM)
        except Exception:
            cam.start_preview(Preview.NULL)

    cam.start()
    _picam2 = cam
    return _picam2

def stop_camera():
    """Stop preview/stream and release the camera if it was started."""
    global _picam2
    if _picam2 is None:
        return
    try:
        # Picamera2 exposes stop_preview() in recent versions; guard just in case.
        if hasattr(_picam2, "stop_preview"):
            _picam2.stop_preview()
    except Exception:
        pass
    try:
        _picam2.stop()
    except Exception:
        pass
    try:
        _picam2.close()
    except Exception:
        pass
    _picam2 = None
