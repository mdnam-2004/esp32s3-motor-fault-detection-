#include "model_inference.h"
#include "motor_fault_config.h"

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "esp_log.h"
#include <cstring>
#include <cmath>

static const char *TAG = "MODEL_INFER";

extern const uint8_t model_start[] asm("_binary_motor_fault_int8_tflite_start");
extern const uint8_t model_end[]   asm("_binary_motor_fault_int8_tflite_end");

static constexpr int kArenaSize = 80 * 1024;
static uint8_t arena[kArenaSize] __attribute__((aligned(16)));

static const tflite::Model      *s_model  = nullptr;
static tflite::MicroInterpreter *s_interp = nullptr;
static TfLiteTensor             *s_input  = nullptr;
static TfLiteTensor             *s_output = nullptr;

extern "C" esp_err_t model_inference_init(void)
{
    s_model = tflite::GetModel(model_start);
    if (s_model->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "Schema mismatch: %lu vs %d",
                 (unsigned long)s_model->version(), TFLITE_SCHEMA_VERSION);
        return ESP_FAIL;
    }

    static tflite::MicroMutableOpResolver<10> resolver;
    resolver.AddConv2D();
    resolver.AddMaxPool2D();
    resolver.AddReshape();
    resolver.AddFullyConnected();
    resolver.AddSoftmax();
    resolver.AddQuantize();
    resolver.AddDequantize();
    resolver.AddPad();
    resolver.AddMean();
    resolver.AddExpandDims();

    static tflite::MicroInterpreter interp(s_model, resolver, arena, kArenaSize);
    s_interp = &interp;

    if (s_interp->AllocateTensors() != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors() failed");
        return ESP_FAIL;
    }

    s_input  = s_interp->input(0);
    s_output = s_interp->output(0);

    ESP_LOGI(TAG, "OK | arena: %zu / %d bytes", s_interp->arena_used_bytes(), kArenaSize);
    ESP_LOGI(TAG, "Input [%d][%d][%d] type=%d",
             s_input->dims->data[0], s_input->dims->data[1],
             s_input->dims->data[2], s_input->type);
    ESP_LOGI(TAG, "Output [%d][%d] type=%d",
             s_output->dims->data[0], s_output->dims->data[1], s_output->type);

    return ESP_OK;
}

extern "C" esp_err_t model_inference_run(const int8_t *input, float *probs, int *pred_class)
{
    if (!s_interp || !input || !probs || !pred_class)
        return ESP_ERR_INVALID_ARG;

    memcpy(s_input->data.int8, input, WINDOW_SIZE * N_CHANNELS);

    if (s_interp->Invoke() != kTfLiteOk) {
        ESP_LOGE(TAG, "Invoke() failed");
        return ESP_FAIL;
    }

    const int8_t *out = s_output->data.int8;

    for (int i = 0; i < N_CLASSES; i++)
        probs[i] = (out[i] - OUTPUT_ZERO_POINT) * OUTPUT_SCALE;

    float max_val = probs[0];
    for (int i = 1; i < N_CLASSES; i++)
        if (probs[i] > max_val) max_val = probs[i];

    float sum = 0.0f;
    for (int i = 0; i < N_CLASSES; i++) {
        probs[i] = expf(probs[i] - max_val);
        sum += probs[i];
    }
    for (int i = 0; i < N_CLASSES; i++)
        probs[i] /= sum;

    int best = 0;
    for (int i = 1; i < N_CLASSES; i++)
        if (probs[i] > probs[best]) best = i;

    *pred_class = best;
    return ESP_OK;
}
