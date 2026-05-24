from pathlib import Path
import csv
import sys

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "dataset_error"
OUTPUT_DIR = BASE_DIR / "dataset_error_removed_col4"

print(f"BASE_DIR   : {BASE_DIR}")
print(f"INPUT_DIR  : {INPUT_DIR}")
print(f"OUTPUT_DIR : {OUTPUT_DIR}")

if not INPUT_DIR.exists():
    print(f"\n[ERROR] Không tìm thấy thư mục input: {INPUT_DIR}")
    sys.exit(1)

csv_files = list(INPUT_DIR.rglob("*.csv"))

print(f"\nTìm thấy {len(csv_files)} file CSV")

if not csv_files:
    print("[ERROR] Không tìm thấy file CSV nào trong dataset_error")
    sys.exit(1)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

processed = 0

for input_path in csv_files:
    relative_path = input_path.relative_to(INPUT_DIR)
    output_path = OUTPUT_DIR / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, "r", newline="", encoding="utf-8") as fin, \
         open(output_path, "w", newline="", encoding="utf-8") as fout:

        reader = csv.reader(fin)
        writer = csv.writer(fout)

        for row in reader:
            if len(row) >= 4:
                del row[3]
            writer.writerow(row)

    processed += 1
    print(f"Đã xử lý: {input_path.name}")

print(f"\nXong. Đã xử lý {processed} file.")
print(f"File output nằm ở: {OUTPUT_DIR}")