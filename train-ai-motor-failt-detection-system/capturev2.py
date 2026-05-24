import serial
import csv
import re
import time
import sys
from datetime import datetime

PORT     = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD     = int(sys.argv[2]) if len(sys.argv) > 2 else 921600
DURATION = int(sys.argv[3]) if len(sys.argv) > 3 else 300

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

ts_str   = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"realtime_log_{ts_str}.csv"

def fmt_time(secs):
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"

def main():
    print("=" * 80)
    print(f"  Motor Fault — Realtime Logger (moi inference, chi tiet ms)")
    print(f"  Port : {PORT}  |  Baud : {BAUD}  |  Duration : {fmt_time(DURATION)}")
    print(f"  Output : {filename}")
    print("=" * 80)
    print("Nhan Ctrl+C de dung som.\n")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(f"[LOI] Khong mo duoc cong {PORT}: {e}")
        return

    session_start = time.time()
    row_count     = 0
    last_label    = None

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "row",
            "wall_time_ms",        # thoi gian may tinh chinh xac den ms
            "esp_timestamp_s",     # timestamp tu esp_timer (s.ms)
            "label",
            "prob_Tat",
            "prob_Binh_thuong",
            "prob_Lech_tam",
            "inference_count",
            "session_elapsed_ms",  # ms ke tu khi bat capture
            "label_changed",       # 1 neu nhan vua doi, 0 neu giu nguyen
        ])
        f.flush()

        print(f"{'#':>5}  {'Wall time (ms)':>16}  {'Label':>12}  "
              f"{'Tat':>7}  {'BT':>7}  {'LT':>7}  "
              f"{'Elapsed':>10}  {'Changed':>8}")
        print("-" * 82)

        try:
            while True:
                now     = time.time()
                elapsed = now - session_start

                if elapsed >= DURATION:
                    print(f"\n  >> Het {fmt_time(DURATION)} — tu dong dung.")
                    break

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

                # Lay chinh xac thoi diem nhan duoc dong nay
                recv_time  = time.time()
                elapsed_ms = round((recv_time - session_start) * 1000)

                # Wall time chinh xac den ms
                wall_ms = datetime.now().strftime("%H:%M:%S.%f")[:12]

                esp_ts, label, p0, p1, p2, infer = m.groups()
                changed = 1 if label != last_label else 0
                last_label = label
                row_count += 1

                writer.writerow([
                    row_count,
                    wall_ms,
                    esp_ts,
                    label,
                    p0, p1, p2,
                    infer,
                    elapsed_ms,
                    changed,
                ])
                f.flush()

                # In terminal — highlight khi doi nhan
                changed_str = "<<< DOI" if changed else ""
                print(f"{row_count:>5}  {wall_ms:>16}  {label:>12}  "
                      f"{float(p0):>7.3f}  {float(p1):>7.3f}  {float(p2):>7.3f}  "
                      f"{elapsed_ms:>8}ms  {changed_str}")

        except KeyboardInterrupt:
            elapsed = round(time.time() - session_start, 1)
            print(f"\n  >> Ctrl+C — dung sau {elapsed}s.")

    # Thong ke cuoi phien
    change_count = 0
    label_counts = {}
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['label_changed'] == '1':
                change_count += 1
            lbl = row['label']
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

    elapsed_total = round(time.time() - session_start, 1)
    print("\n" + "=" * 80)
    print(f"  Thoi gian chay    : {fmt_time(elapsed_total)} ({elapsed_total}s)")
    print(f"  Tong inference    : {row_count}")
    print(f"  So lan doi nhan   : {change_count}")
    print(f"  Phan bo nhan:")
    for lbl, cnt in sorted(label_counts.items()):
        pct = cnt / row_count * 100 if row_count else 0
        print(f"    {lbl:<15}: {cnt:>4} lan ({pct:.1f}%)")
    print(f"  File da luu       : {filename}")
    print("=" * 80)

if __name__ == "__main__":
    main()