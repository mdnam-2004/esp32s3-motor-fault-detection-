#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include "esp_err.h"
#include <stdint.h>

esp_err_t model_inference_init(void);
esp_err_t model_inference_run(const int8_t *input, float *probs, int *pred_class);

#ifdef __cplusplus
}
#endif
