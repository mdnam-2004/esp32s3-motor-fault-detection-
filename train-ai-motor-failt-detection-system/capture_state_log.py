import serial
import csv
import re
import time
import sys
from datetime import datetime

PORT      = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD      = int(sys.argv[2]) if len(sys.argv) > 2 else 921600
INTERVAL  = 10  # giây, ghi định kỳ

# Format từ ESP32: PREDICT:CSV,<s.ms>,<label>,<p0>,<p1>,<p2>,<infer_count>
PATTERN = re.compile(
    r'PREDICT:CSV,'
    r'(\d+\.\d+),'
    r'([a-zA-Z_]+),'
    r'([\d.]+),'
    r'([\d.]+),'
    r'([\d.]+),'
    r'(\d+)'
)

# ── Nhập tên file ──────────────────────────────────────────────────────────
ts_str       = datetime.now().strftime("%Y%m%d_%H%M%S")
default_name = f"state_log_{ts_str}"
print(f"Ten file CSV (Enter de dung ten mac dinh: '{default_name}.csv'): ", end="", flush=True)
custom_name = input().strip()
if custom_name:
    if custom_name.lower().endswith(".csv"):
        custom_name = custom_name[:-4]
    filename = f"{custom_name}.csv"
else:
    filename = f"{default_name}.csv"

# ── Nhập thời lượng ────────────────────────────────────────────────────────
default_minutes = sys.argv[3] if len(sys.argv) > 3 else "5"
print(f"Thoi luong ghi (phut, Enter de dung mac dinh: {default_minutes} phut): ", end="", flush=True)
duration_input = input().strip()
if duration_input:
    try:
        DURATION = int(float(duration_input) * 60)
        if DURATION <= 0:
            raise ValueError
    except ValueError:
        print(f"[!] Gia tri khong hop le, dung mac dinh {default_minutes} phut.")
        DURATION = int(float(default_minutes) * 60)
else:
    DURATION = int(float(default_minutes) * 60)

def fmt_time(secs):
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"

def write_row(writer, f, row_count, wall_time, cur_esp_ts, cur_label,
              cur_p0, cur_p1, cur_p2, cur_infer, elapsed, event_type, remaining):
    writer.writerow([
        wall_time, cur_esp_ts, cur_label,
        cur_p0, cur_p1, cur_p2,
        cur_infer, round(elapsed, 1), event_type,
    ])
    f.flush()
    print(f"{row_count:>4}  {wall_time:>10}  {cur_label:>12}  "
          f"{float(cur_p0):>7.3f}  {float(cur_p1):>7.3f}  {float(cur_p2):>7.3f}  "
          f"{elapsed:>8.1f}s  {event_type:>10}  {fmt_time(remaining):>8}")

def main():
    print("=" * 78)
    print(f"  Motor Fault Logger — interval {INTERVAL}s + ghi ngay khi doi nhan")
    print(f"  Port : {PORT}  |  Baud : {BAUD}  |  Duration : {fmt_time(DURATION)} ({DURATION}s)")
    print(f"  Output : {filename}")
    print("=" * 78)
    print("Nhan Ctrl+C de dung som.\n")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(f"[LOI] Khong mo duoc cong {PORT}: {e}")
        return

    session_start = time.time()
    last_write    = -INTERVAL
    row_count     = 0

    cur_label  = "unknown"
    cur_esp_ts = "0.000"
    cur_p0 = cur_p1 = cur_p2 = "0.0000"
    cur_infer  = "0"
    data_received = False

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "wall_time", "esp_timestamp_s", "label",
            "prob_Tat", "prob_Binh_thuong", "prob_Lech_tam",
            "inference_count", "session_elapsed_s", "event_type",
        ])
        f.flush()

        print(f"{'#':>4}  {'Wall time':>10}  {'Label':>12}  "
              f"{'Tat':>7}  {'BT':>7}  {'LT':>7}  "
              f"{'Elapsed':>9}  {'Type':>10}  {'Con lai':>8}")
        print("-" * 78)

        try:
            while True:
                now     = time.time()
                elapsed = now - session_start

                if elapsed >= DURATION:
                    print(f"\n  >> Het {fmt_time(DURATION)} — tu dong dung.")
                    break

                remaining = DURATION - elapsed

                if data_received and elapsed - last_write >= INTERVAL:
                    last_write = elapsed
                    row_count += 1
                    write_row(writer, f, row_count,
                              datetime.now().strftime("%H:%M:%S"),
                              cur_esp_ts, cur_label,
                              cur_p0, cur_p1, cur_p2, cur_infer,
                              elapsed, "INTERVAL", remaining)

                raw = ser.readline()
                if not raw:
                    continue
                try:
                    line = raw.decode('utf-8', errors='replace').strip()
                except Exception:
                    continue

                m = PATTERN.search(line)
                if not m:
                    continue

                esp_ts, label, p0, p1, p2, infer = m.groups()

                if label != cur_label:
                    cur_esp_ts, cur_label  = esp_ts, label
                    cur_p0, cur_p1, cur_p2 = p0, p1, p2
                    cur_infer              = infer
                    data_received          = True
                    last_write             = elapsed
                    row_count += 1
                    write_row(writer, f, row_count,
                              datetime.now().strftime("%H:%M:%S"),
                              cur_esp_ts, cur_label,
                              cur_p0, cur_p1, cur_p2, cur_infer,
                              round(elapsed, 1), "CHANGE", remaining)
                else:
                    cur_esp_ts, cur_p0, cur_p1, cur_p2, cur_infer = esp_ts, p0, p1, p2, infer
                    data_received = True

        except KeyboardInterrupt:
            elapsed = round(time.time() - session_start, 1)
            print(f"\n  >> Ctrl+C — dung sau {elapsed}s.")

    elapsed_total = round(time.time() - session_start, 1)
    change_count   = sum(1 for _ in open(filename) if ',CHANGE,' in _)
    interval_count = sum(1 for _ in open(filename) if ',INTERVAL,' in _)
    print("\n" + "=" * 78)
    print(f"  Thoi gian chay  : {fmt_time(elapsed_total)} ({elapsed_total}s)")
    print(f"  Tong dong ghi   : {row_count}")
    print(f"    CHANGE        : {change_count} lan doi nhan")
    print(f"    INTERVAL      : {interval_count} lan ghi dinh ky")
    print(f"  File da luu     : {filename}")
    print("=" * 78)

if __name__ == "__main__":
    main()