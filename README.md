# SwipeMouse

Control your mouse cursor, clicks, and scrolling using just your webcam and one hand, no external hardware. Built with MediaPipe for hand landmark detection and OpenCV for the video pipeline.

## Features

- **Cursor movement**: point your index finger inside the on-screen active zone to move the mouse, mapped and gain-amplified so you don't need to reach every corner of the frame to reach every corner of your screen.
- **Click**: pinch your thumb and index finger together.
- **Scroll**: close your hand into a fist and drag it up or down. Scroll amount is proportional to how far you drag. Open your hand to release.
- Live on-screen debug info: FPS counter, all 21 hand landmark indices, handedness (Left/Right), pinch distance, and active control zone.

## Requirements

- Windows (cursor movement uses a direct Windows API call via `ctypes`; on Mac/Linux you'd need to swap `move_cursor()`/`click_cursor()` for `pyautogui.moveTo()`/`pyautogui.click()`, slower but portable)
- A working webcam
- Python 3.9–3.12 (MediaPipe does not yet support the newest Python releases reliably)

## Setup

```
pip install -r requirements.txt
python gesture_control.py
```

Press `q` with the window focused to quit.

## Known issue: MediaPipe `solutions` module

MediaPipe releases from roughly 0.10.31 onward have a packaging bug where `mediapipe.solutions` doesn't exist, raising `AttributeError: module 'mediapipe' has no attribute 'solutions'` on import, regardless of OS or clean install. This is why `requirements.txt` pins `mediapipe==0.10.14`, a version from before the regression. If you hit that error anyway, confirm the pinned version actually installed with `pip show mediapipe`, since pip sometimes serves a cached wheel silently.

## Tuning

All the constants that control feel and sensitivity sit at the top of `gesture_control.py`:

| Constant | What it does |
|---|---|
| `FRAME_MARGIN` | Shrinks the active control zone inside the camera frame. Smaller zone = less hand travel needed to reach screen edges. |
| `CURSOR_GAIN` | Amplifies fingertip movement away from the zone center, so you don't need to physically reach the true edge of the zone to reach a screen corner. |
| `SMOOTHENING` | Cursor motion smoothing. Higher = smoother but laggier, lower = snappier but jitterier. |
| `CLICK_THRESHOLD_ENTER` / `CLICK_THRESHOLD_EXIT` | Pinch distance (pixels) to start/end a click. Two thresholds (hysteresis) stop finger jitter right at the boundary from eating the click. |
| `CURL_RATIO_THRESHOLD` | How tightly fingers must curl to count toward a fist. |
| `CLASP_FINGER_COUNT` | How many of the 4 fingers (thumb excluded) must be curled to register a fist. |
| `DRAG_SENSITIVITY` | Scroll amount per pixel of vertical fist movement. |

Values are tuned for a fairly typical laptop webcam at arm's length. Different cameras, resolutions, and desk setups will need different numbers, watch the live debug overlays (pinch distance, palm circle) while adjusting.

## How it works, briefly

- MediaPipe's `Hands` solution returns 21 3D landmarks per detected hand every frame, plus a Left/Right classification.
- Cursor position maps the index fingertip (landmark 8) from a defined rectangle in the camera frame to full screen coordinates, smoothed with exponential averaging.
- Click detection measures pixel distance between the thumb tip (landmark 4) and index tip (landmark 8).
- Fist detection compares each fingertip's distance from the wrist to its own knuckle's distance from the wrist. This ratio is orientation and scale invariant, so it works regardless of how the hand is angled.
- Only the first hand MediaPipe reports each frame drives cursor/click/scroll, so a second hand in frame doesn't fight for control.

## License

MIT
