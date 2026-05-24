# 🔧 ESP32-S3 Motor Fault Detection System

Hệ thống phát hiện lỗi động cơ theo thời gian thực sử dụng ESP32-S3, cảm biến gia tốc (IMU), và mô hình học sâu 1D-CNN được tối ưu hóa cho thiết bị nhúng (TFLite INT8).

---

## 📋 Mục lục

- [Tổng quan hệ thống](#-tổng-quan-hệ-thống)
- [Kiến trúc](#-kiến-trúc)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Các lớp phân loại](#-các-lớp-phân-loại)
- [Yêu cầu phần cứng](#-yêu-cầu-phần-cứng)
- [Yêu cầu phần mềm](#-yêu-cầu-phần-mềm)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
  - [1. Thu thập dữ liệu](#1-thu-thập-dữ-liệu)
  - [2. Huấn luyện mô hình](#2-huấn-luyện-mô-hình)
  - [3. Kiểm tra mô hình (PC)](#3-kiểm-tra-mô-hình-pc)
  - [4. Deploy lên ESP32-S3](#4-deploy-lên-esp32-s3)
  - [5. Ghi log trạng thái](#5-ghi-log-trạng-thái)
- [Thông số mô hình](#-thông-số-mô-hình)
- [Kết quả](#-kết-quả)

---

## 🧠 Tổng quan hệ thống

Hệ thống đọc dữ liệu gia tốc 3 trục (ax, ay, az) từ cảm biến IMU gắn trên động cơ qua giao tiếp UART ở tốc độ 100 Hz. Dữ liệu được xử lý thành các cửa sổ thời gian (sliding window) và đưa qua mô hình 1D-CNN để phân loại trạng thái động cơ trong thời gian thực.

```
[Động cơ + IMU] → UART (921600 baud) → [ESP32-S3] → TFLite INT8 Inference → [Kết quả phân loại]
                                                                              ↓
                                                                    Web Server / UART Output
```

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────┐
│                  PIPELINE                           │
│                                                     │
│  IMU (100Hz)                                        │
│     ↓                                               │
│  Sliding Window (200 samples / 2s, stride 50)       │
│     ↓                                               │
│  Z-score Normalization                              │
│     ↓                                               │
│  1D-CNN (INT8 quantized)                            │
│     ↓                                               │
│  Softmax → [Tắt | Bình thường | Lệch tâm]          │
└─────────────────────────────────────────────────────┘
```

**Kiến trúc mô hình 1D-CNN:**

| Layer | Filters | Kernel | Output |
|-------|---------|--------|--------|
| Conv1D + BN + ReLU + MaxPool | 32 | 5 | 100 × 32 |
| Conv1D + BN + ReLU + MaxPool | 64 | 5 | 50 × 64 |
| Conv1D + BN + ReLU + MaxPool | 128 | 3 | 25 × 128 |
| Conv1D + BN + ReLU + GAP | 128 | 3 | 128 |
| Dense + Dropout | 64 | — | 64 |
| Dense (Softmax) | 3 | — | 3 |

---

## 📁 Cấu trúc thư mục

```
project/
│
├── train-ai/                        # Scripts Python (PC)
│   ├── collection_dataset.py        # Thu thập dữ liệu từ UART → CSV
│   ├── traninng.py                  # Huấn luyện mô hình 1D-CNN
│   ├── test_model.py                # Kiểm tra mô hình real-time trên PC
│   ├── capture_state_log.py         # Ghi log trạng thái (interval + change)
│   ├── capturev2.py                 # Ghi log real-time mỗi inference
│   ├── scrip.py                     # Tiền xử lý CSV (xóa cột thừa)
│   └── dataset/                     # Dữ liệu huấn luyện (CSV per label)
│       ├── Tat/
│       ├── Binh_thuong/
│       └── Lech_tam/
│
├── esp32-firmware/                  # Firmware ESP32-S3 (ESP-IDF)
│   ├── fault_motor_main.c           # Main application
│   ├── fault_motor_main_collect.c   # Chế độ thu thập dữ liệu
│   ├── model_inference.cc           # TFLite Micro inference engine
│   ├── model_inference.h
│   ├── web_server.c                 # HTTP web server
│   ├── web_server.h
│   ├── motor_fault_config.h         # Cấu hình norm + quantization (auto-generated)
│   ├── model/                       # TFLite model binary
│   ├── CMakeLists.txt
│   ├── idf_component.yml
│   └── Kconfig.projbuild
│
└── output/                          # Kết quả huấn luyện (auto-generated)
    ├── motor_fault_int8.tflite
    ├── motor_fault_config.h
    ├── deployment_info.json
    ├── norm_stats.json
    ├── best_model.keras
    ├── training_history.png
    └── confusion_matrix.png
```

---

## 🏷️ Các lớp phân loại

| ID | Label | Mô tả |
|----|-------|-------|
| 0 | `Tat` | Động cơ tắt / không hoạt động |
| 1 | `Binh_thuong` | Động cơ hoạt động bình thường |
| 2 | `Lech_tam` | Động cơ bị lệch tâm (unbalance) |

---

## ⚙️ Yêu cầu phần cứng

- **Vi điều khiển:** ESP32-S3
- **Cảm biến:** IMU 3 trục (ví dụ: MPU-6050, ICM-42688-P, ...) kết nối qua SPI/I2C → ESP32
- **Kết nối PC:** USB-UART (921600 baud, COM9 mặc định)
- **Động cơ:** Bất kỳ motor DC/AC có thể gắn cảm biến rung

---

## 💻 Yêu cầu phần mềm

### PC (Python)

```bash
pip install pyserial numpy pandas scikit-learn tensorflow matplotlib seaborn
```

Hoặc dùng TFLite Runtime (nhẹ hơn, chỉ cho inference):

```bash
pip install tflite-runtime pyserial numpy
```

### ESP32-S3 (Firmware)

- [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/latest/) v5.x
- TFLite Micro component (thêm vào `idf_component.yml`)

---

## 🚀 Hướng dẫn sử dụng

### 1. Thu thập dữ liệu

Kết nối ESP32 ở chế độ thu thập dữ liệu, sau đó chạy:

```bash
python collection_dataset.py
```

- Chọn **label** (Tắt / Bình thường / Lệch tâm) và **thời gian ghi**
- Dữ liệu được lưu tự động vào `dataset/<label>/`
- Định dạng CSV: `ax, ay, az` (đơn vị g, tần số 100 Hz)

> **Khuyến nghị:** Thu thập tối thiểu **30 phút** mỗi lớp để đạt độ chính xác cao.

### 2. Huấn luyện mô hình

```bash
python traninng.py
```

Pipeline tự động thực hiện:
1. Load & segment dữ liệu (sliding window 2s, stride 0.5s)
2. Z-score normalization
3. Train/Val/Test split (80/10/10)
4. Huấn luyện 1D-CNN (tối đa 80 epochs, early stopping)
5. Export TFLite INT8
6. Sinh file `motor_fault_config.h` cho ESP32

Kết quả lưu tại `output/`.

### 3. Kiểm tra mô hình (PC)

Kiểm tra inference real-time trực tiếp từ UART:

```bash
python test_model.py
```

Hiển thị kết quả phân loại theo thời gian thực với thanh xác suất và thời gian inference (ms).

### 4. Deploy lên ESP32-S3

```bash
# Copy model vào firmware
cp output/motor_fault_int8.tflite esp32-firmware/model/
cp output/motor_fault_config.h esp32-firmware/

# Build và flash
cd esp32-firmware
idf.py build flash monitor
```

### 5. Ghi log trạng thái

**Log đầy đủ mỗi inference (ms-level):**

```bash
python capturev2.py COM11 921600 300
# COM11: cổng, 921600: baud, 300: thời gian (giây)
```

**Log theo interval + khi đổi nhãn:**

```bash
python capture_state_log.py COM11 921600 5
# Tham số cuối: thời lượng (phút)
```

---

## 📊 Thông số mô hình

| Thông số | Giá trị |
|----------|---------|
| Tần số lấy mẫu | 100 Hz |
| Cửa sổ thời gian | 200 samples (2.0 giây) |
| Bước trượt (stride) | 50 samples (0.5 giây) |
| Số kênh đầu vào | 3 (ax, ay, az) |
| Định dạng model | TFLite INT8 |
| Framework ESP32 | TFLite Micro (ESP-IDF) |

---

## 📈 Kết quả

Sau khi huấn luyện, kết quả được lưu tại `output/`:

- `training_history.png` — Đồ thị Accuracy & Loss
- `confusion_matrix.png` — Ma trận nhầm lẫn (count & %)
- `deployment_info.json` — Thông tin deploy và độ chính xác

---

## 📝 Ghi chú

- Chỉnh sửa `SERIAL_PORT` trong các script Python nếu cổng COM khác COM9/COM11
- File `motor_fault_config.h` được sinh tự động sau mỗi lần train — **không chỉnh sửa thủ công**
- Dataset không được commit lên Git (thêm `dataset/` vào `.gitignore`)

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE) để biết thêm chi tiết.
