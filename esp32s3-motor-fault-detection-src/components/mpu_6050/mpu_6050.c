#include "mpu_6050.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static mpu6050_config_t s_cfg;

static float accel_sensitivity(mpu6050_accel_fs_t fs)
{
    switch (fs) {
        case MPU6050_ACCEL_FS_2G:  return 16384.0f;
        case MPU6050_ACCEL_FS_4G:  return 8192.0f;
        case MPU6050_ACCEL_FS_8G:  return 4096.0f;
        case MPU6050_ACCEL_FS_16G: return 2048.0f;
        default:                   return 16384.0f;
    }
}

static float gyro_sensitivity(mpu6050_gyro_fs_t fs)
{
    switch (fs) {
        case MPU6050_GYRO_FS_250DPS:  return 131.0f;
        case MPU6050_GYRO_FS_500DPS:  return 65.5f;
        case MPU6050_GYRO_FS_1000DPS: return 32.8f;
        case MPU6050_GYRO_FS_2000DPS: return 16.4f;
        default:                      return 131.0f;
    }
}

static esp_err_t write_reg(uint8_t reg, uint8_t data)
{
    uint8_t buf[2] = {reg, data};
    return i2c_master_write_to_device(
        s_cfg.i2c_port, s_cfg.device_address,
        buf, sizeof(buf), pdMS_TO_TICKS(100));
}

static esp_err_t read_regs(uint8_t reg, uint8_t *data, size_t len)
{
    return i2c_master_write_read_device(
        s_cfg.i2c_port, s_cfg.device_address,
        &reg, 1, data, len, pdMS_TO_TICKS(100));
}

esp_err_t mpu6050_init(const mpu6050_config_t *config)
{
    if (!config) return ESP_ERR_INVALID_ARG;
    memcpy(&s_cfg, config, sizeof(s_cfg));
    esp_err_t ret;

    ret = write_reg(MPU6050_REG_PWR_MGMT_1, 0x80);
    if (ret != ESP_OK) return ret;
    vTaskDelay(pdMS_TO_TICKS(100));

    ret = write_reg(MPU6050_REG_PWR_MGMT_1, 0x01);
    if (ret != ESP_OK) return ret;

    ret = write_reg(MPU6050_REG_PWR_MGMT_2, 0x00);
    if (ret != ESP_OK) return ret;

    ret = write_reg(MPU6050_REG_CONFIG, s_cfg.dlpf);
    if (ret != ESP_OK) return ret;

    uint16_t sr = s_cfg.sample_rate_hz;
    if (sr == 0 || sr > 1000) sr = 1000;
    uint8_t div = (1000 / sr) - 1;
    ret = write_reg(MPU6050_REG_SMPLRT_DIV, div);
    if (ret != ESP_OK) return ret;

    ret = write_reg(MPU6050_REG_GYRO_CONFIG, s_cfg.gyro_fs << 3);
    if (ret != ESP_OK) return ret;

    ret = write_reg(MPU6050_REG_ACCEL_CONFIG, s_cfg.accel_fs << 3);
    if (ret != ESP_OK) return ret;

    return ESP_OK;
}

esp_err_t mpu6050_read_raw(mpu6050_raw_data_t *raw)
{
    if (!raw) return ESP_ERR_INVALID_ARG;
    uint8_t buf[14];
    esp_err_t ret = read_regs(MPU6050_REG_ACCEL_XOUT_H, buf, 14);
    if (ret != ESP_OK) return ret;

    raw->ax = (int16_t)((buf[0] << 8) | buf[1]);
    raw->ay = (int16_t)((buf[2] << 8) | buf[3]);
    raw->az = (int16_t)((buf[4] << 8) | buf[5]);
    raw->temp = (int16_t)((buf[6] << 8) | buf[7]);
    raw->gx = (int16_t)((buf[8] << 8) | buf[9]);
    raw->gy = (int16_t)((buf[10] << 8) | buf[11]);
    raw->gz = (int16_t)((buf[12] << 8) | buf[13]);
    return ESP_OK;
}

esp_err_t mpu6050_read_scaled(mpu6050_scaled_data_t *scaled)
{
    if (!scaled) return ESP_ERR_INVALID_ARG;
    mpu6050_raw_data_t raw;
    esp_err_t ret = mpu6050_read_raw(&raw);
    if (ret != ESP_OK) return ret;

    float acc_sens  = accel_sensitivity(s_cfg.accel_fs);
    float gyro_sens = gyro_sensitivity(s_cfg.gyro_fs);

    scaled->ax_g = raw.ax / acc_sens;
    scaled->ay_g = raw.ay / acc_sens;
    scaled->az_g = raw.az / acc_sens;
    scaled->gx_dps = raw.gx / gyro_sens;
    scaled->gy_dps = raw.gy / gyro_sens;
    scaled->gz_dps = raw.gz / gyro_sens;
    scaled->temp_c = (raw.temp / 340.0f) + 36.53f;
    return ESP_OK;
}