#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "driver/i2c.h"
#include "driver/uart.h"
#include "hal/uart_types.h"

#include "mpu_6050.h"

static const char *TAG = "DATASET";

#define I2C_MASTER_NUM      I2C_NUM_0
#define I2C_MASTER_SDA_IO   8
#define I2C_MASTER_SCL_IO   9
#define I2C_MASTER_FREQ_HZ  400000
#define MPU6050_ADDR        0x68

#define PC_UART_NUM         UART_NUM_0
#define PC_UART_TX_PIN      43
#define PC_UART_RX_PIN      44
#define PC_BAUDRATE         921600

#define SAMPLE_PERIOD_MS    10

static void pc_uart_init(void)
{
    uart_config_t cfg = {
        .baud_rate  = PC_BAUDRATE,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(PC_UART_NUM, 4096, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(PC_UART_NUM, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(PC_UART_NUM,
                                 PC_UART_TX_PIN, PC_UART_RX_PIN,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

static void i2c_master_init(void)
{
    i2c_config_t i2c_conf = {
        .mode             = I2C_MODE_MASTER,
        .sda_io_num       = I2C_MASTER_SDA_IO,
        .scl_io_num       = I2C_MASTER_SCL_IO,
        .sda_pullup_en    = GPIO_PULLUP_ENABLE,
        .scl_pullup_en    = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_MASTER_FREQ_HZ,
    };
    ESP_ERROR_CHECK(i2c_param_config(I2C_MASTER_NUM, &i2c_conf));
    ESP_ERROR_CHECK(i2c_driver_install(I2C_MASTER_NUM, i2c_conf.mode, 0, 0, 0));
}

static void mpu_init(void)
{
    mpu6050_config_t mpu_cfg = {
        .i2c_port        = I2C_MASTER_NUM,
        .device_address  = MPU6050_ADDR,
        .accel_fs        = MPU6050_ACCEL_FS_4G,
        .gyro_fs         = MPU6050_GYRO_FS_500DPS,
        .dlpf            = MPU6050_DLPF_94HZ,
        .sample_rate_hz  = 1000,
    };
    ESP_ERROR_CHECK(mpu6050_init(&mpu_cfg));
}

static void task_send_data(void *arg)
{
    (void)arg;

    mpu6050_scaled_data_t sensor;
    char line[64];
    TickType_t last_wake = xTaskGetTickCount();

    ESP_LOGI(TAG, "Bat dau gui du lieu @ %d Hz", 1000 / SAMPLE_PERIOD_MS);

    while (1) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(SAMPLE_PERIOD_MS));

        if (mpu6050_read_scaled(&sensor) != ESP_OK)
            continue;

        int n = snprintf(line, sizeof(line),
                         "%.6f,%.6f,%.6f\r\n",
                         sensor.ax_g,
                         sensor.ay_g,
                         sensor.az_g);

        if (n > 0)
            uart_write_bytes(PC_UART_NUM, line, n);
    }
}

void app_main(void)
{
    pc_uart_init();
    i2c_master_init();
    mpu_init();

    const char *banner =
        "\r\n"
        "======================================\r\n"
        "  MPU6050 Dataset Recorder\r\n"
        "  3 kenh: ax, ay, az [g] @ 100 Hz\r\n"
        "  Format: CSV, khong header\r\n"
        "======================================\r\n\r\n";
    uart_write_bytes(PC_UART_NUM, banner, strlen(banner));

    xTaskCreate(task_send_data, "send_data", 4096, NULL, 5, NULL);

    ESP_LOGI(TAG, "He thong san sang");
}