
#pragma once

static const float NORM_MEAN[3] = {0.048073f, -0.182877f, 0.907200f};
static const float NORM_STD[3]  = {0.209444f,  0.146853f,  0.084246f};

static const float  INPUT_SCALE       = 0.08001178f;
static const int8_t INPUT_ZERO_POINT  = 11;
static const float  OUTPUT_SCALE      = 0.00390625f;
static const int8_t OUTPUT_ZERO_POINT = -128;

#define WINDOW_SIZE   200
#define STRIDE_SIZE   50
#define N_CHANNELS    3
#define N_CLASSES     3

static const char* CLASS_NAMES[N_CLASSES] = {
    "Tat",
    "Binh_thuong",
    "Lech_tam",
};
