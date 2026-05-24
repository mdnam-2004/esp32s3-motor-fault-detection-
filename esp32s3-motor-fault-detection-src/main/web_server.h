#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include "esp_err.h"
#include <stdint.h>

typedef struct {
    int      pred_class;
    float    probs[3];
    float    ax;
    float    ay;
    float    az;
    uint32_t inference_count;
} motor_status_t;

extern motor_status_t g_motor_status;

void wifi_init_softap(void);
esp_err_t start_webserver(void);

#ifdef __cplusplus
}
#endif
