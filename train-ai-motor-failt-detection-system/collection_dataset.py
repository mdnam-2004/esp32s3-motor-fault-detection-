import os
import sys
import csv
import time
import threading
from datetime import datetime

import serial


SERIAL_PORT  = "COM9"
BAUDRATE     = 921600
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT  = os.path.join(SCRIPT_DIR, "dataset")
PRINT_EVERY  = 1.0


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


class SerialReader(threading.Thread):
    def __init__(self, ser: serial.Serial):
        super().__init__(daemon=True)
        self.ser = ser
        self._stop  = threading.Event()
        self.lock   = threading.Lock()
        self.latest = None
        self.total  = 0
        self.bad    = 0

    def run(self):
        while not self._stop.is_set():
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                s = raw.decode("utf-8", errors="ignore").strip()
                if not s:
                    continue

                lo = s.lower()
                if any(kw in lo for kw in ["====", "mode", "format", "san sang",
                                            "data col", "kenh", "[i]", "[w]", "[e]"]):
                    continue

                parts = s.split(",")
                if len(parts) != 3:
                    with self.lock:
                        self.bad += 1
                    continue

                try:
                    ax, ay, az = float(parts[0]), float(parts[1]), float(parts[2])
                except ValueError:
                    with self.lock:
                        self.bad += 1
                    continue

                with self.lock:
                    self.latest = (ax, ay, az)
                    self.total += 1

            except Exception:
                time.sleep(0.01)

    def stop(self):
        self._stop.set()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def make_path(label, minutes):
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(OUTPUT_ROOT, label)
    ensure_dir(folder)
    return os.path.join(folder, f"{label}_{minutes}p_{ts}.csv")


def record(label: str, minutes: int, reader: SerialReader):
    duration_s = minutes * 60
    path       = make_path(label, minutes)
    end_time   = time.time() + duration_s
    rows       = 0

    with reader.lock:
        start_total = reader.total
        start_bad   = reader.bad
    last_written = start_total
    last_seen    = start_total
    last_print   = 0.0
    start        = time.time()

    print(f"\n[REC] Nhan   : {label}")
    print(f"[REC] Thoi gian: {minutes} phut")
    print(f"[REC] File   : {path}")
    print("[REC] Nhan 'Q' hoac ESC de dung som.\n")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        while True:
            now = time.time()
            if now >= end_time:
                break

            key = _get_key()
            if key and (key.lower() == "q" or ord(key) == 27):
                print("\n[REC] Dung som theo yeu cau.")
                break

            with reader.lock:
                sample = reader.latest
                total  = reader.total
                bad    = reader.bad

            if sample is not None and total != last_written:
                last_written = total
                writer.writerow([f"{sample[0]:.6f}",
                                  f"{sample[1]:.6f}",
                                  f"{sample[2]:.6f}"])
                rows += 1

            if now - last_print >= PRINT_EVERY:
                elapsed = now - start
                remain  = max(0.0, end_time - now)
                dlines  = total - last_seen
                last_seen = total
                rate_in  = dlines / max(PRINT_EVERY, 1e-6)
                rate_w   = rows   / max(elapsed, 1e-6)
                print(
                    f"\r[REC] {int(elapsed//60):02d}:{int(elapsed%60):02d} elapsed | "
                    f"{int(remain//60):02d}:{int(remain%60):02d} con lai | "
                    f"Ghi: {rows} dong ({rate_w:.1f}/s) | "
                    f"UART: ~{rate_in:.1f} dong/s | "
                    f"Bad: {bad - start_bad}",
                    end="", flush=True,
                )
                last_print = now

            time.sleep(0.001)

    with reader.lock:
        total_in  = reader.total - start_total
        total_bad = reader.bad   - start_bad

    print("\n")
    print(f"[REC] XONG! Da ghi    : {rows} dong")
    print(f"[REC] UART nhan duoc  : {total_in} dong (bad: {total_bad})")
    print(f"[REC] File            : {path}\n")


def show_label_menu(labels: list[str]) -> str:
    print("\n=== Chon nhan (label) ===")
    for i, lbl in enumerate(labels, 1):
        print(f"  {i}) {lbl}")
    print(f"  N) Them nhan moi")
    print(f"  0) Xem lai danh sach nhan da co trong dataset/")

    while True:
        sel = input("Lua chon: ").strip()

        if sel == "0":
            show_existing_labels()
            continue

        if sel.lower() == "n":
            new_lbl = input("Ten nhan moi (khong dau cach, dung '_'): ").strip()
            new_lbl = new_lbl.replace(" ", "_")
            if not new_lbl:
                print("Ten khong hop le.")
                continue
            if new_lbl not in labels:
                labels.append(new_lbl)
                print(f"  -> Da them nhan: {new_lbl}")
            return new_lbl

        if sel.isdigit():
            idx = int(sel) - 1
            if 0 <= idx < len(labels):
                return labels[idx]

        print("Lua chon khong hop le. Thu lai.")


def show_existing_labels():
    if not os.path.isdir(OUTPUT_ROOT):
        print("  (Chua co du lieu nao trong dataset/)")
        return
    folders = [d for d in os.listdir(OUTPUT_ROOT)
               if os.path.isdir(os.path.join(OUTPUT_ROOT, d))]
    if not folders:
        print("  (Chua co nhan nao trong dataset/)")
    else:
        print(f"  Cac nhan hien co trong '{OUTPUT_ROOT}/': {', '.join(sorted(folders))}")


def choose_minutes() -> int:
    options = {"1": 15, "2": 30, "3": 45, "4": 60, "5": 5, "6": 10}
    print("\n=== Thoi gian ghi ===")
    print("  1)  5 phut   (thu nghiem nhanh)")
    print("  2) 10 phut")
    print("  3) 15 phut")
    print("  4) 30 phut")
    print("  5) 45 phut")
    print("  6) 60 phut")
    print("  C) Nhap tuy chinh (phut)")

    remap = {"1": 5, "2": 10, "3": 15, "4": 30, "5": 45, "6": 60}

    while True:
        sel = input("Lua chon: ").strip()
        if sel in remap:
            return remap[sel]
        if sel.lower() == "c":
            try:
                m = int(input("Nhap so phut: ").strip())
                if m > 0:
                    return m
            except ValueError:
                pass
        print("Lua chon khong hop le. Thu lai.")


def main():
    default_labels: list[str] = [
        "Tat",
        "Binh_thuong_1",
        "Lech_tam_1",
        "Binh_thuong_2",
        "Lech_tam_2",
    ]

    print("=" * 45)
    print("  ESP32 UART Dataset Recorder")
    print(f"  Port: {SERIAL_PORT}  Baudrate: {BAUDRATE}")
    print("  Du lieu: ax, ay, az [g]  @  100 Hz")
    print("=" * 45)
    show_existing_labels()

    label   = show_label_menu(default_labels)
    minutes = choose_minutes()

    print(f"\nMo UART: {SERIAL_PORT} @ {BAUDRATE} baud ...")
    try:
        ser = serial.Serial(
            port     = SERIAL_PORT,
            baudrate = BAUDRATE,
            bytesize = serial.EIGHTBITS,
            parity   = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
            timeout  = 0.2,
        )
    except serial.SerialException as e:
        print(f"[LOI] Khong mo duoc UART: {e}")
        sys.exit(1)

    reader = SerialReader(ser)
    reader.start()

    print("\nSan sang.")
    print(f"Nhan  : {label}  |  Thoi gian: {minutes} phut")
    print("Nhan 'A' de bat dau thu.")
    print("Nhan Ctrl+C de thoat.\n")

    try:
        while True:
            key = _get_key()
            if key and key.lower() == "a":
                record(label, minutes, reader)

                label   = show_label_menu(default_labels)
                minutes = choose_minutes()
                print(f"\nNhan: {label} | {minutes} phut")
                print("Nhan 'A' de thu phien moi, Ctrl+C de thoat.\n")

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nThoat.")

    finally:
        reader.stop()
        time.sleep(0.05)
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()