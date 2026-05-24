import os
import sys
import time
import json
import threading
import collections
import numpy as np

import serial

try:
    from tflite_runtime.interpreter import Interpreter
    print("[INFO] Dùng tflite_runtime")
except ImportError:
    try:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
        print("[INFO] Dùng tensorflow.lite.Interpreter")
    except ImportError:
        print("[ERROR] Cần cài: pip install tflite-runtime  hoặc  pip install tensorflow")
        sys.exit(1)


SERIAL_PORT = "COM9"
BAUDRATE    = 921600

_HERE       = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(_HERE, "output", "motor_fault_int8.tflite")
DEPLOY_JSON = os.path.join(_HERE, "output", "deployment_info.json")

SAMPLE_RATE = 100
WINDOW_SIZE = 200
STRIDE_SIZE = 50

CLASSES = ["Tat", "Binh_thuong", "Lech_tam"]

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

CLASS_COLORS = [RED, GREEN, YELLOW]
CLASS_ICONS  = ["🔴", "✅", "⚠️ "]


def load_deployment_info(json_path):
    if not os.path.exists(json_path):
        print(f"[ERROR] Không tìm thấy: {json_path}")
        print("        Chạy training.py trước!")
        sys.exit(1)
    with open(json_path) as f:
        info = json.load(f)
    return info


def _get_key():
    if os.name == "nt":
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            try:
                return ch.decode("utf-8", errors="ignore")
            except Exception:
                return None
        return None
    else:
        import select, termios, tty
        fd = sys.stdin.fileno()
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if not dr:
            return None
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class SerialLineReader(threading.Thread):
    def __init__(self, ser: serial.Serial):
        super().__init__(daemon=True)
        self.ser = ser
        self._stop = threading.Event()
        self.lock = threading.Lock()
        self.latest_sample = None
        self.total_lines = 0
        self.bad_lines = 0

    def run(self):
        while not self._stop.is_set():
            try:
                line = self.ser.readline()
                if not line:
                    continue
                s = line.decode("utf-8", errors="ignore").strip()
                if not s:
                    continue

                lo = s.lower()
                if any(kw in lo for kw in ["====", "mode", "format", "san sang",
                                            "data col", "[i]", "[w]", "[e]"]):
                    continue

                parts = s.split(",")
                if len(parts) != 3:
                    with self.lock:
                        self.bad_lines += 1
                    continue

                try:
                    ax = float(parts[0])
                    ay = float(parts[1])
                    az = float(parts[2])
                except ValueError:
                    with self.lock:
                        self.bad_lines += 1
                    continue

                with self.lock:
                    self.latest_sample = (ax, ay, az)
                    self.total_lines += 1

            except Exception:
                time.sleep(0.01)

    def stop(self):
        self._stop.set()


class MotorFaultInference:
    def __init__(self, model_path, deploy_info):
        self.interp = Interpreter(model_path=model_path)
        self.interp.allocate_tensors()

        self.inp_det = self.interp.get_input_details()[0]
        self.out_det = self.interp.get_output_details()[0]

        self.mean = np.array(deploy_info["norm_mean"], dtype=np.float32)
        self.std  = np.array(deploy_info["norm_std"],  dtype=np.float32)

        self.inp_scale = deploy_info["input_scale"]
        self.inp_zp    = deploy_info["input_zero_point"]
        self.out_scale = deploy_info["output_scale"]
        self.out_zp    = deploy_info["output_zero_point"]

        print(f"  Input  dtype : {self.inp_det['dtype']}")
        print(f"  Output dtype : {self.out_det['dtype']}")
        print(f"  Input  shape : {self.inp_det['shape']}")

    def predict(self, window: np.ndarray):
        norm = (window - self.mean) / self.std
        q = np.round(norm / self.inp_scale + self.inp_zp)
        q = np.clip(q, -128, 127).astype(np.int8)
        q = q[np.newaxis, ...]

        self.interp.set_tensor(self.inp_det["index"], q)
        self.interp.invoke()

        out_int8 = self.interp.get_tensor(self.out_det["index"])
        probs = (out_int8.astype(np.float32) - self.out_zp) * self.out_scale
        probs = probs[0]

        probs = np.exp(probs - probs.max())
        probs /= probs.sum()

        return int(np.argmax(probs)), probs


def render_bar(prob: float, width: int = 20) -> str:
    filled = int(round(prob * width))
    return "█" * filled + "░" * (width - filled)


def print_result(pred_idx, probs, inference_ms, total_inferences):
    print(f"\n{'─'*55}")
    print(f"  {BOLD}Inference #{total_inferences}{RESET}  |  {CYAN}Time: {inference_ms:.1f} ms{RESET}")
    print(f"{'─'*55}")
    for i, (cls, prob) in enumerate(zip(CLASSES, probs)):
        color  = CLASS_COLORS[i]
        icon   = CLASS_ICONS[i]
        bar    = render_bar(prob)
        marker = f"  ◄ {BOLD}PREDICTED{RESET}" if i == pred_idx else ""
        print(f"  {icon} {color}{cls:<14}{RESET}  {bar}  {prob*100:5.1f}%{marker}")
    print(f"{'─'*55}")
    print(f"  {BOLD}→ KẾT QUẢ: {CLASS_COLORS[pred_idx]}{CLASS_ICONS[pred_idx]} {CLASSES[pred_idx]}{RESET}")
    print(f"{'─'*55}")


def main():
    print("=" * 55)
    print(f"  {BOLD}MOTOR FAULT - REAL-TIME INFERENCE TEST{RESET}")
    print("=" * 55)

    print("\n[1] Loading deployment info...")
    info = load_deployment_info(DEPLOY_JSON)
    print(f"  Trained accuracy : {info.get('test_accuracy_pct', 'N/A')}%")
    print(f"  TFLite size      : {info.get('tflite_size_kb', 'N/A')} KB")
    print(f"  Classes          : {info.get('classes', CLASSES)}")

    print("\n[2] Loading TFLite INT8 model...")
    if not os.path.exists(MODEL_PATH):
        print(f"  [ERROR] Không tìm thấy: {MODEL_PATH}")
        sys.exit(1)
    engine = MotorFaultInference(MODEL_PATH, info)
    print("  Model loaded OK ✓")

    print(f"\n[3] Mở UART: {SERIAL_PORT} @ {BAUDRATE}...")
    try:
        ser = serial.Serial(
            port=SERIAL_PORT, baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE, timeout=0.2,
        )
    except serial.SerialException as e:
        print(f"  [ERROR] {e}")
        print(f"  Kiểm tra lại cổng COM (hiện tại: {SERIAL_PORT})")
        sys.exit(1)

    reader = SerialLineReader(ser)
    reader.start()
    print("  UART OK ✓")

    window_buf = collections.deque(maxlen=WINDOW_SIZE)

    print(f"\n[4] Chờ đủ {WINDOW_SIZE} samples ({WINDOW_SIZE/SAMPLE_RATE:.1f}s)...")
    print("    Nhấn Q hoặc Ctrl+C để thoát\n")

    total_inferences = 0
    last_total_seen  = 0
    samples_since_last_inference = 0
    last_status_t    = time.time()
    pred_counts      = [0] * len(CLASSES)

    try:
        while True:
            key = _get_key()
            if key and key.lower() in ("q", "\x1b"):
                print("\nThoát theo yêu cầu.")
                break

            with reader.lock:
                sample      = reader.latest_sample
                total_lines = reader.total_lines
                bad         = reader.bad_lines

            if sample is not None and total_lines != last_total_seen:
                last_total_seen = total_lines
                window_buf.append(sample)
                samples_since_last_inference += 1

                if (len(window_buf) == WINDOW_SIZE and
                        samples_since_last_inference >= STRIDE_SIZE):

                    samples_since_last_inference = 0
                    win_arr = np.array(window_buf, dtype=np.float32)

                    t0 = time.perf_counter()
                    pred_idx, probs = engine.predict(win_arr)
                    inf_ms = (time.perf_counter() - t0) * 1000

                    total_inferences += 1
                    pred_counts[pred_idx] += 1
                    print_result(pred_idx, probs, inf_ms, total_inferences)

            if len(window_buf) < WINDOW_SIZE and time.time() - last_status_t >= 1.0:
                last_status_t = time.time()
                bar = render_bar(len(window_buf) / WINDOW_SIZE, 30)
                print(f"\r  Đang thu: [{bar}] {len(window_buf)}/{WINDOW_SIZE} "
                      f"UART: {total_lines} lines  Bad: {bad}",
                      end="", flush=True)

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\n\nDừng...")

    finally:
        reader.stop()
        time.sleep(0.05)
        try:
            ser.close()
        except Exception:
            pass

    print("\n" + "=" * 55)
    print(f"  {BOLD}TỔNG KẾT SESSION{RESET}")
    print("=" * 55)
    print(f"  Tổng inferences : {total_inferences}")
    for i, cls in enumerate(CLASSES):
        pct = pred_counts[i] / total_inferences * 100 if total_inferences > 0 else 0
        print(f"  {CLASS_ICONS[i]} {cls:<14}: {pred_counts[i]:4d} lần  ({pct:.1f}%)")
    print("=" * 55)


if __name__ == "__main__":
    main()