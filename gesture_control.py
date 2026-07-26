import cv2
import mediapipe as mp
import time
import math
import ctypes
import pyautogui

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=0,  # lite model, faster on CPU
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always grab the newest frame, not a queued old one
prev_time = 0

CLICK_THRESHOLD_ENTER = 22   # pinch distance must drop below this to start a click
CLICK_THRESHOLD_EXIT = 38    # must rise above this to count as released, prevents flicker at the boundary
click_state = {"Left": False, "Right": False}

# --- cursor control setup ---
screen_w, screen_h = pyautogui.size()
FRAME_MARGIN = 100
SMOOTHENING = 4
CURSOR_GAIN = 1.6
prev_screen_x, prev_screen_y = screen_w // 2, screen_h // 2

# --- direct Windows mouse control, bypasses pyautogui call overhead ---
user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def move_cursor(x, y):
    user32.SetCursorPos(int(x), int(y))


def click_cursor():
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


# --- clasp-and-drag scroll setup ---
CURL_RATIO_THRESHOLD = 1.1   # fingertip-to-wrist distance vs MCP-to-wrist distance; below this = curled
CLASP_FINGER_COUNT = 3        # how many of the 4 fingers must be curled to count as a clasp
DRAG_SENSITIVITY = 15         # scroll units per pixel of vertical drag movement
clasp_state = {"Left": False, "Right": False}
clasp_last_y = {"Left": None, "Right": None}

while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    cv2.rectangle(
        frame, (FRAME_MARGIN, FRAME_MARGIN), (w - FRAME_MARGIN, h - FRAME_MARGIN),
        (255, 0, 255), 2
    )

    if result.multi_hand_landmarks:
        for hand_index, (hand_landmarks, handedness) in enumerate(zip(
            result.multi_hand_landmarks, result.multi_handedness
        )):
            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=3),
                mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2),
            )

            label = handedness.classification[0].label

            for idx, lm in enumerate(hand_landmarks.landmark):
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.putText(
                    frame, str(idx), (cx + 5, cy - 3),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, (255, 255, 0), 1
                )

            wrist_x = int(hand_landmarks.landmark[0].x * w)
            wrist_y = int(hand_landmarks.landmark[0].y * h)
            cv2.putText(
                frame, label.upper(), (wrist_x - 20, wrist_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2
            )

            # --- fist / clasp detection ---
            # a finger counts as curled when its tip is no farther from the wrist
            # than its own knuckle is, which is true regardless of hand rotation
            wrist_lm = hand_landmarks.landmark[0]

            def dist_to_wrist(idx):
                lm = hand_landmarks.landmark[idx]
                return math.hypot(lm.x - wrist_lm.x, lm.y - wrist_lm.y)

            finger_pairs = [(8, 5), (12, 9), (16, 13), (20, 17)]  # (tip, mcp)
            curled_count = sum(
                1 for tip_idx, mcp_idx in finger_pairs
                if dist_to_wrist(tip_idx) < dist_to_wrist(mcp_idx) * CURL_RATIO_THRESHOLD
            )
            is_clasping = curled_count >= CLASP_FINGER_COUNT

            palm_x = int(hand_landmarks.landmark[9].x * w)
            palm_y = int(hand_landmarks.landmark[9].y * h)

            if is_clasping:
                cv2.circle(frame, (palm_x, palm_y), 20, (0, 0, 255), 3)
                cv2.putText(
                    frame, "CLASP", (palm_x - 30, palm_y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                )

                if not clasp_state[label]:
                    # just closed the fist this frame, start of a drag, don't scroll yet
                    clasp_last_y[label] = palm_y
                else:
                    delta_y = palm_y - clasp_last_y[label]
                    if delta_y != 0:
                        pyautogui.scroll(int(-delta_y * DRAG_SENSITIVITY))
                        cv2.arrowedLine(
                            frame, (palm_x, clasp_last_y[label]), (palm_x, palm_y),
                            (0, 0, 255), 3, tipLength=0.3
                        )
                    clasp_last_y[label] = palm_y

                click_state[label] = False  # don't let a fist's thumb/index proximity fire a click

            else:
                # pinch / click detection, only runs on an open hand
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                tx, ty = int(thumb_tip.x * w), int(thumb_tip.y * h)
                ix, iy = int(index_tip.x * w), int(index_tip.y * h)

                dist = math.hypot(ix - tx, iy - ty)
                # hysteresis: harder to enter a pinch, easier to stay in one, prevents flicker at the boundary
                threshold = CLICK_THRESHOLD_EXIT if click_state[label] else CLICK_THRESHOLD_ENTER
                is_pinching = dist < threshold

                line_color = (0, 0, 255) if is_pinching else (0, 255, 255)
                cv2.line(frame, (tx, ty), (ix, iy), line_color, 2)

                mid_x, mid_y = (tx + ix) // 2, (ty + iy) // 2
                cv2.putText(
                    frame, str(int(dist)), (mid_x, mid_y - 10),
                    cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255), 1
                )

                if is_pinching and not click_state[label]:
                    print(f"CLICK - {label} hand")
                    if hand_index == 0:
                        click_cursor()

                if is_pinching:
                    cv2.circle(frame, (mid_x, mid_y), 15, (0, 0, 255), cv2.FILLED)
                    cv2.putText(
                        frame, "CLICK", (ix + 15, iy - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2
                    )

                click_state[label] = is_pinching

                # cursor movement, primary hand only, paused while clasping
                if hand_index == 0:
                    fx, fy = int(hand_landmarks.landmark[8].x * w), int(hand_landmarks.landmark[8].y * h)

                    zone_w = w - 2 * FRAME_MARGIN
                    zone_h = h - 2 * FRAME_MARGIN
                    zone_cx = FRAME_MARGIN + zone_w / 2
                    zone_cy = FRAME_MARGIN + zone_h / 2

                    offset_x = (fx - zone_cx) * CURSOR_GAIN
                    offset_y = (fy - zone_cy) * CURSOR_GAIN

                    target_x = screen_w / 2 + (offset_x / (zone_w / 2)) * (screen_w / 2)
                    target_y = screen_h / 2 + (offset_y / (zone_h / 2)) * (screen_h / 2)

                    target_x = min(max(target_x, 0), screen_w - 1)
                    target_y = min(max(target_y, 0), screen_h - 1)

                    smooth_x = prev_screen_x + (target_x - prev_screen_x) / SMOOTHENING
                    smooth_y = prev_screen_y + (target_y - prev_screen_y) / SMOOTHENING

                    move_cursor(smooth_x, smooth_y)
                    prev_screen_x, prev_screen_y = smooth_x, smooth_y

                    cv2.circle(frame, (fx, fy), 10, (255, 0, 255), cv2.FILLED)

            clasp_state[label] = is_clasping

    curr_time = time.time()
    fps = 1 / (curr_time - prev_time) if prev_time else 0
    prev_time = curr_time

    cv2.putText(
        frame, f"FPS : {int(fps)}", (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
    )

    cv2.imshow("Gesture Control", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
