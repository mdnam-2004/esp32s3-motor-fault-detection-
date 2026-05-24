#pragma once

#include <stdint.h>
#include "esp_err.h"
#include "driver/i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MPU6050_ADDR_LOW   0x68
#define MPU6050_ADDR_HIGH  0x69

#define MPU6050_REG_SMPLRT_DIV      0x19
#define MPU6050_REG_CONFIG          0x1A
#define MPU6050_REG_GYRO_CONFIG     0x1B
#define MPU6050_REG_ACCEL_CONFIG    0x1C
#define MPU6050_REG_ACCEL_XOUT_H    0x3B
#define MPU6050_REG_PWR_MGMT_1      0x6B
#define MPU6050_REG_PWR_MGMT_2      0x6C

typedef enum {
    MPU6050_ACCEL_FS_2G  = 0,
    MPU6050_ACCEL_FS_4G  = 1,
    MPU6050_ACCEL_FS_8G  = 2,
    MPU6050_ACCEL_FS_16G = 3,
} mpu6050_accel_fs_t;

typedef enum {
    MPU6050_GYRO_FS_250DPS  = 0,
    MPU6050_GYRO_FS_500DPS  = 1,
    MPU6050_GYRO_FS_1000DPS = 2,
    MPU6050_GYRO_FS_2000DPS = 3,
} mpu6050_gyro_fs_t;

typedef enum {
    MPU6050_DLPF_260HZ = 0,
    MPU6050_DLPF_184HZ = 1,
    MPU6050_DLPF_94HZ  = 2,
    MPU6050_DLPF_44HZ  = 3,
    MPU6050_DLPF_21HZ  = 4,
    MPU6050_DLPF_10HZ  = 5,
    MPU6050_DLPF_5HZ   = 6,
} mpu6050_dlpf_t;

typedef struct {
    i2c_port_t i2c_port;
    uint8_t device_address;

    mpu6050_accel_fs_t accel_fs;
    mpu6050_gyro_fs_t  gyro_fs;
    mpu6050_dlpf_t     dlpf;
    uint16_t sample_rate_hz;
} mpu6050_config_t;

typedef struct {
    int16_t ax, ay, az;
    int16_t temp;
    int16_t gx, gy, gz;
} mpu6050_raw_data_t;

typedef struct {
    float ax_g, ay_g, az_g;
    float gx_dps, gy_dps, gz_dps;
    float temp_c;
} mpu6050_scaled_data_t;

esp_err_t mpu6050_init(const mpu6050_config_t *config);
esp_err_t mpu6050_read_raw(mpu6050_raw_data_t *raw);
esp_err_t mpu6050_read_scaled(mpu6050_scaled_data_t *scaled);

#ifdef __cplusplus
}
#endif