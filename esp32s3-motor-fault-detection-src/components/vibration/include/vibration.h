#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    float sample_rate;
    float hp_alpha;
    uint16_t window_size;

    float prev_x;
    float prev_y;
    float prev_z;

    float prev_hp_x;
    float prev_hp_y;
    float prev_hp_z;

    float *buffer;
    uint16_t index;
    uint16_t count;
    float sum_sq;

    float peak;

} vibration_t;

typedef struct
{
    float rms_g;
    float rms_ms2;
    float peak_g;
    float crest_factor;
} vibration_result_t;
bool vibration_init(vibration_t *vib,
                    float sample_rate,
                    float hp_cutoff_hz,
                    uint16_t window_size);

void vibration_update(vibration_t *vib,
                      float ax_g,
                      float ay_g,
                      float az_g);
bool vibration_get_result(vibration_t *vib,
                          vibration_result_t *result);
void vibration_deinit(vibration_t *vib);

#ifdef __cplusplus
}
#endif