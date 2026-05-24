#include "vibration.h"
#include <stdlib.h>
#include <math.h>

#define GRAVITY 9.80665f

static float compute_hp_alpha(float sample_rate, float cutoff)
{
    float dt = 1.0f / sample_rate;
    float rc = 1.0f / (2.0f * M_PI * cutoff);
    return rc / (rc + dt);
}

bool vibration_init(vibration_t *vib,
                    float sample_rate,
                    float hp_cutoff_hz,
                    uint16_t window_size)
{
    if (!vib || window_size == 0)
        return false;

    vib->sample_rate = sample_rate;
    vib->hp_alpha = compute_hp_alpha(sample_rate, hp_cutoff_hz);
    vib->window_size = window_size;

    vib->prev_x = vib->prev_y = vib->prev_z = 0;
    vib->prev_hp_x = vib->prev_hp_y = vib->prev_hp_z = 0;

    vib->index = 0;
    vib->count = 0;
    vib->sum_sq = 0;
    vib->peak = 0;

    vib->buffer = calloc(window_size, sizeof(float));
    if (!vib->buffer)
        return false;

    return true;
}

void vibration_update(vibration_t *vib,
                      float ax_g,
                      float ay_g,
                      float az_g)
{
    float hp_x = vib->hp_alpha *
                 (vib->prev_hp_x + ax_g - vib->prev_x);

    float hp_y = vib->hp_alpha *
                 (vib->prev_hp_y + ay_g - vib->prev_y);

    float hp_z = vib->hp_alpha *
                 (vib->prev_hp_z + az_g - vib->prev_z);

    vib->prev_x = ax_g;
    vib->prev_y = ay_g;
    vib->prev_z = az_g;

    vib->prev_hp_x = hp_x;
    vib->prev_hp_y = hp_y;
    vib->prev_hp_z = hp_z;

    float mag = sqrtf(hp_x * hp_x +
                      hp_y * hp_y +
                      hp_z * hp_z);

    if (vib->count < vib->window_size)
    {
        vib->buffer[vib->index] = mag;
        vib->sum_sq += mag * mag;
        vib->count++;
    }
    else
    {
        float old = vib->buffer[vib->index];
        vib->sum_sq -= old * old;

        vib->buffer[vib->index] = mag;
        vib->sum_sq += mag * mag;
    }

    if (mag > vib->peak)
        vib->peak = mag;

    vib->index++;
    if (vib->index >= vib->window_size)
        vib->index = 0;
}

bool vibration_get_result(vibration_t *vib,
                          vibration_result_t *result)
{
    if (!vib || !result)
        return false;

    if (vib->count < vib->window_size)
        return false;

    float rms = sqrtf(vib->sum_sq / vib->window_size);

    result->rms_g = rms;
    result->rms_ms2 = rms * GRAVITY;
    result->peak_g = vib->peak;

    if (rms > 0.0001f)
        result->crest_factor = vib->peak / rms;
    else
        result->crest_factor = 0;

    vib->peak = 0;

    return true;
}

void vibration_deinit(vibration_t *vib)
{
    if (!vib) return;

    if (vib->buffer)
    {
        free(vib->buffer);
        vib->buffer = NULL;
    }
}