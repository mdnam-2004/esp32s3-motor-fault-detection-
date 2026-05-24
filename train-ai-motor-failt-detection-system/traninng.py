import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks
import json
DATASET_ROOT = r"D:\Study_work\2026_Semester_08\thayDuan\esp32s3-motor-fault-detection-system\train-ai-motor-failt-detection-system\dataset"
OUTPUT_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

CLASSES = [
    "Tat",
    "Binh_thuong",
    "Lech_tam",
]
CLASS_DISPLAY = CLASSES  

SAMPLE_RATE   = 100    
WINDOW_SEC    = 2.0    
STRIDE_SEC    = 0.5   
N_CHANNELS    = 3    

EPOCHS        = 80
BATCH_SIZE    = 32
LEARNING_RATE = 1e-3
RANDOM_SEED   = 42

EARLY_STOP_PATIENCE = 15
REDUCE_LR_PATIENCE  = 7
REDUCE_LR_FACTOR    = 0.5
REDUCE_LR_MIN       = 1e-6
WINDOW_SIZE = int(SAMPLE_RATE * WINDOW_SEC)   
STRIDE_SIZE = int(SAMPLE_RATE * STRIDE_SEC)  
N_CLASSES   = len(CLASSES)

os.makedirs(OUTPUT_DIR, exist_ok=True)
np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)

print("=" * 60)
print("  MOTOR FAULT DETECTION PIPELINE  (3 Classes)")
print("=" * 60)
print(f"  Dataset      : {DATASET_ROOT}")
print(f"  Output       : {OUTPUT_DIR}/")
print(f"  Sample rate  : {SAMPLE_RATE} Hz")
print(f"  Window       : {WINDOW_SIZE} samples ({WINDOW_SEC}s)")
print(f"  Stride       : {STRIDE_SIZE} samples ({STRIDE_SEC}s)")
print(f"  Classes      : {CLASS_DISPLAY}")
print(f"  Epochs       : {EPOCHS}  |  Batch: {BATCH_SIZE}  |  LR: {LEARNING_RATE}")
print("=" * 60)

def load_and_segment(dataset_root, classes, window_size, stride_size):
    X_all, y_all = [], []

    for label, cls in enumerate(classes):
        folder    = os.path.join(dataset_root, cls)
        csv_files = glob.glob(os.path.join(folder, "*.csv"))

        if not csv_files:
            print(f"  [WARNING] Không tìm thấy CSV trong: {folder}")
            continue

        print(f"\n  [{cls}] - {len(csv_files)} file(s)")
        cls_segments = 0

        for fpath in csv_files:
            try:
                df   = pd.read_csv(fpath, header=None, names=["x", "y", "z"])
                data = df.values.astype(np.float32)

                start = 0
                while start + window_size <= len(data):
                    X_all.append(data[start:start + window_size])
                    y_all.append(label)
                    start += stride_size
                    cls_segments += 1

            except Exception as e:
                print(f"    [ERROR] {os.path.basename(fpath)}: {e}")

        print(f"    → {cls_segments} segments")

    X = np.array(X_all, dtype=np.float32)
    y = np.array(y_all, dtype=np.int32)
    return X, y


print("\n[STEP 1] Loading & segmenting data...")
X, y = load_and_segment(DATASET_ROOT, CLASSES, WINDOW_SIZE, STRIDE_SIZE)

print(f"\n  Total segments : {X.shape[0]}")
print(f"  X shape        : {X.shape}  (samples, window, channels)")
dist = {CLASS_DISPLAY[i]: int(v) for i, v in enumerate(np.bincount(y, minlength=N_CLASSES))}
print(f"  y distribution : {dist}")


print("\n[STEP 2] Normalizing (z-score per channel)...")

mean = X.mean(axis=(0, 1))
std  = X.std(axis=(0, 1))
std  = np.where(std == 0, 1e-8, std)

X_norm = (X - mean) / std

stats = {"mean": mean.tolist(), "std": std.tolist()}
with open(os.path.join(OUTPUT_DIR, "norm_stats.json"), "w") as f:
    json.dump(stats, f, indent=2)
print(f"  Mean: {mean.round(4)}")
print(f"  Std : {std.round(4)}")
print(f"  → Saved to {OUTPUT_DIR}/norm_stats.json")
print("\n[STEP 3] Splitting 80/10/10...")

X_train, X_temp, y_train, y_temp = train_test_split(
    X_norm, y, test_size=0.20,
    random_state=RANDOM_SEED, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50,
    random_state=RANDOM_SEED, stratify=y_temp
)

print(f"  Train : {X_train.shape[0]} samples")
print(f"  Val   : {X_val.shape[0]} samples")
print(f"  Test  : {X_test.shape[0]} samples")

y_train_oh = tf.keras.utils.to_categorical(y_train, num_classes=N_CLASSES)
y_val_oh   = tf.keras.utils.to_categorical(y_val,   num_classes=N_CLASSES)
y_test_oh  = tf.keras.utils.to_categorical(y_test,  num_classes=N_CLASSES)

def build_1dcnn(input_shape, num_classes):
    inp = keras.Input(shape=input_shape, name="input")
    x = layers.Conv1D(32, kernel_size=5, padding="same", name="conv1")(inp)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.MaxPooling1D(pool_size=2)(x)
    x = layers.Dropout(0.2)(x)

    x = layers.Conv1D(64, kernel_size=5, padding="same", name="conv2")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.MaxPooling1D(pool_size=2)(x)
    x = layers.Dropout(0.2)(x)

    x = layers.Conv1D(128, kernel_size=3, padding="same", name="conv3")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.MaxPooling1D(pool_size=2)(x)
    x = layers.Dropout(0.3)(x)

    x = layers.Conv1D(128, kernel_size=3, padding="same", name="conv4")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.GlobalAveragePooling1D()(x)

    x = layers.Dense(64, activation="relu", name="fc1")(x)
    x = layers.Dropout(0.4)(x)
    out = layers.Dense(num_classes, activation="softmax", name="output")(x)

    return keras.Model(inp, out, name="MotorFault_1DCNN_3cls")


print("\n[STEP 4] Building 1D-CNN model (3 classes)...")
model = build_1dcnn(input_shape=(WINDOW_SIZE, N_CHANNELS), num_classes=N_CLASSES)
model.summary()

total_params = model.count_params()
est_size_kb  = total_params * 4 / 1024
print(f"\n  Total params : {total_params:,}")
print(f"  Est. size    : {est_size_kb:.1f} KB (float32)")
print(f"  Est. INT8    : {est_size_kb/4:.1f} KB (sau quantize)")

print("\n[STEP 5] Compiling & Training...")

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

cb_list = [
    callbacks.EarlyStopping(
        monitor="val_accuracy", patience=EARLY_STOP_PATIENCE,
        restore_best_weights=True, verbose=1
    ),
    callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=REDUCE_LR_FACTOR,
        patience=REDUCE_LR_PATIENCE, min_lr=REDUCE_LR_MIN, verbose=1
    ),
    callbacks.ModelCheckpoint(
        filepath=os.path.join(OUTPUT_DIR, "best_model.keras"),
        monitor="val_accuracy",
        save_best_only=True, verbose=0
    ),
    callbacks.CSVLogger(os.path.join(OUTPUT_DIR, "training_log.csv"))
]

history = model.fit(
    X_train, y_train_oh,
    validation_data=(X_val, y_val_oh),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    callbacks=cb_list,
    verbose=1
)

model = keras.models.load_model(os.path.join(OUTPUT_DIR, "best_model.keras"))


print("\n[STEP 6] Evaluating on Test set...")

test_loss, test_acc = model.evaluate(X_test, y_test_oh, verbose=0)
print(f"\n  Test Loss     : {test_loss:.4f}")
print(f"  Test Accuracy : {test_acc*100:.2f}%")

y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
print("\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=CLASS_DISPLAY))

cm     = confusion_matrix(y_test, y_pred)
cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=CLASS_DISPLAY, yticklabels=CLASS_DISPLAY, ax=axes[0])
axes[0].set_title("Confusion Matrix (counts)", fontsize=13)
axes[0].set_ylabel("True Label")
axes[0].set_xlabel("Predicted Label")
axes[0].tick_params(axis='x', rotation=30)

sns.heatmap(cm_pct, annot=True, fmt=".1f", cmap="Greens",
            xticklabels=CLASS_DISPLAY, yticklabels=CLASS_DISPLAY, ax=axes[1])
axes[1].set_title("Confusion Matrix (%)", fontsize=13)
axes[1].set_ylabel("True Label")
axes[1].set_xlabel("Predicted Label")
axes[1].tick_params(axis='x', rotation=30)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "confusion_matrix.png"), dpi=150)
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].plot(history.history["accuracy"],     label="Train Acc")
axes[0].plot(history.history["val_accuracy"], label="Val Acc")
axes[0].set_title("Accuracy")
axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Accuracy")
axes[0].legend(); axes[0].grid(True, alpha=0.3)

axes[1].plot(history.history["loss"],     label="Train Loss")
axes[1].plot(history.history["val_loss"], label="Val Loss")
axes[1].set_title("Loss")
axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("Loss")
axes[1].legend(); axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "training_history.png"), dpi=150)
plt.close()
print(f"  → Plots saved to {OUTPUT_DIR}/")


print("\n[STEP 7] Converting to TFLite INT8...")

def representative_dataset():
    indices = np.random.choice(len(X_train), size=min(200, len(X_train)), replace=False)
    for i in indices:
        yield [X_train[i:i+1].astype(np.float32)]

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type  = tf.int8
converter.inference_output_type = tf.int8

tflite_model = converter.convert()

tflite_path = os.path.join(OUTPUT_DIR, "motor_fault_int8.tflite")
with open(tflite_path, "wb") as f:
    f.write(tflite_model)

tflite_size_kb = len(tflite_model) / 1024
print(f"  TFLite INT8 size : {tflite_size_kb:.1f} KB")
print(f"  → Saved: {tflite_path}")


print("\n[STEP 8] Validating TFLite INT8 model...")

interpreter = tf.lite.Interpreter(model_path=tflite_path)
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print(f"  Input  : shape={input_details[0]['shape']}, "
      f"dtype={input_details[0]['dtype'].__name__}, "
      f"scale={input_details[0]['quantization'][0]:.6f}, "
      f"zero_point={input_details[0]['quantization'][1]}")
print(f"  Output : shape={output_details[0]['shape']}, "
      f"dtype={output_details[0]['dtype'].__name__}, "
      f"scale={output_details[0]['quantization'][0]:.6f}, "
      f"zero_point={output_details[0]['quantization'][1]}")

inp_scale = input_details[0]['quantization'][0]
inp_zp    = input_details[0]['quantization'][1]
out_scale = output_details[0]['quantization'][0]
out_zp    = output_details[0]['quantization'][1]

correct        = 0
n_test_samples = min(50, len(X_test))
for i in range(n_test_samples):
    sample      = X_test[i:i+1].astype(np.float32)
    sample_int8 = np.round(sample / inp_scale + inp_zp).astype(np.int8)
    interpreter.set_tensor(input_details[0]['index'], sample_int8)
    interpreter.invoke()
    output       = interpreter.get_tensor(output_details[0]['index'])
    output_float = (output.astype(np.float32) - out_zp) * out_scale
    if np.argmax(output_float) == y_test[i]:
        correct += 1

tflite_acc = correct / n_test_samples * 100
print(f"  TFLite INT8 accuracy (50 samples): {tflite_acc:.1f}%")


quant_info = {
    "input_scale"      : float(inp_scale),
    "input_zero_point" : int(inp_zp),
    "output_scale"     : float(out_scale),
    "output_zero_point": int(out_zp),
    "norm_mean"        : mean.tolist(),
    "norm_std"         : std.tolist(),
    "window_size"      : WINDOW_SIZE,
    "n_channels"       : N_CHANNELS,
    "sample_rate_hz"   : SAMPLE_RATE,
    "stride_size"      : STRIDE_SIZE,
    "classes"          : CLASS_DISPLAY,
    "n_classes"        : N_CLASSES,
    "test_accuracy_pct": round(test_acc * 100, 2),
    "tflite_size_kb"   : round(tflite_size_kb, 1)
}

with open(os.path.join(OUTPUT_DIR, "deployment_info.json"), "w") as f:
    json.dump(quant_info, f, indent=2)
print(f"  → Saved: {OUTPUT_DIR}/deployment_info.json")


print("\n[STEP 10] Generating ESP32 C header...")

c_snippet = f"""
#pragma once

static const float NORM_MEAN[3] = {{{mean[0]:.6f}f, {mean[1]:.6f}f, {mean[2]:.6f}f}};
static const float NORM_STD[3]  = {{{std[0]:.6f}f,  {std[1]:.6f}f,  {std[2]:.6f}f}};

static const float  INPUT_SCALE       = {inp_scale:.8f}f;
static const int8_t INPUT_ZERO_POINT  = {inp_zp};
static const float  OUTPUT_SCALE      = {out_scale:.8f}f;
static const int8_t OUTPUT_ZERO_POINT = {out_zp};

#define WINDOW_SIZE   {WINDOW_SIZE}
#define STRIDE_SIZE   {STRIDE_SIZE}
#define N_CHANNELS    {N_CHANNELS}
#define N_CLASSES     {N_CLASSES}

static const char* CLASS_NAMES[N_CLASSES] = {{
    "Tat",
    "Binh_thuong",
    "Lech_tam",
}};
"""

with open(os.path.join(OUTPUT_DIR, "motor_fault_config.h"), "w") as f:
    f.write(c_snippet)
print(f"  → Saved: {OUTPUT_DIR}/motor_fault_config.h")


print("\n" + "=" * 60)
print("  PIPELINE COMPLETE  (3 Classes)")
print("=" * 60)
print(f"  Test Accuracy    : {test_acc*100:.2f}%")
print(f"  TFLite INT8 size : {tflite_size_kb:.1f} KB")
print(f"\n  Classes:")
for i, c in enumerate(CLASS_DISPLAY):
    print(f"    [{i}] {c}")
print(f"\n  Output files:")
print(f"    {OUTPUT_DIR}/best_model.keras")
print(f"    {OUTPUT_DIR}/motor_fault_int8.tflite")
print(f"    {OUTPUT_DIR}/motor_fault_config.h")
print(f"    {OUTPUT_DIR}/deployment_info.json")
print(f"    {OUTPUT_DIR}/norm_stats.json")
print(f"    {OUTPUT_DIR}/training_history.png")
print(f"    {OUTPUT_DIR}/confusion_matrix.png")
print("=" * 60)
print("\n  ► Bước tiếp theo:")
print("  1. Copy motor_fault_int8.tflite vào ESP32 project")
print("  2. Dùng motor_fault_config.h để preprocess & inference")
print("  3. Dùng TFLite Micro (ESP-IDF component) để load model")
print("=" * 60)