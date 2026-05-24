#include <stdio.h>
#include <string.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "driver/i2c.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "hal/uart_types.h"

#include "mpu_6050.h"
#include "model_inference.h"
#include "motor_fault_config.h"
#include "web_server.h"

static const char *TAG = "MOTOR_FAULT";

#define I2C_MASTER_NUM      I2C_NUM_0
#define I2C_MASTER_SDA_IO   8
#define I2C_MASTER_SCL_IO   9
#define I2C_MASTER_FREQ_HZ  400000
#define MPU6050_ADDR        0x68

#define PC_UART_NUM         UART_NUM_1
#define PC_UART_TX_PIN      17
#define PC_UART_RX_PIN      18
#define PC_BAUDRATE         921600

#define SAMPLE_PERIOD_MS    10

#define LED_GREEN_PIN       4
#define LED_YELLOW_PIN      5
#define LED_RED_PIN         6

static const int LED_PINS[N_CLASSES] = {LED_GREEN_PIN, LED_YELLOW_PIN, LED_RED_PIN};

static void led_init(void)
{
    for (int i = 0; i < N_CLASSES; i++) {
        gpio_reset_pin(LED_PINS[i]);
        gpio_set_direction(LED_PINS[i], GPIO_MODE_OUTPUT);
        gpio_set_level(LED_PINS[i], 0);
    }
}

static void led_set_class(int cls)
{
    for (int i = 0; i < N_CLASSES; i++) {
        gpio_set_level(LED_PINS[i], (i == cls) ? 1 : 0);
    }
}

static void pc_uart_init(void)
{
    uart_config_t cfg = {
        .baud_rate  = PC_BAUDRATE,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT
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
        .sample_rate_hz  = 1000
    };
    ESP_ERROR_CHECK(mpu6050_init(&mpu_cfg));
}


static void preprocess_window(const float raw[][N_CHANNELS], int8_t *out)
{
    for (int i = 0; i < WINDOW_SIZE; i++) {
        for (int c = 0; c < N_CHANNELS; c++) {
            float norm = (raw[i][c] - NORM_MEAN[c]) / NORM_STD[c];
            int q = (int)roundf(norm / INPUT_SCALE) + INPUT_ZERO_POINT;
            if (q < -128) q = -128;
            if (q >  127) q =  127;
            out[i * N_CHANNELS + c] = (int8_t)q;
        }
    }
}

static void update_status(int pred, float *probs, mpu6050_scaled_data_t *sensor)
{
    g_motor_status.pred_class = pred;
    g_motor_status.probs[0] = probs[0];
    g_motor_status.probs[1] = probs[1];
    g_motor_status.probs[2] = probs[2];
    g_motor_status.ax = sensor->ax_g;
    g_motor_status.ay = sensor->ay_g;
    g_motor_status.az = sensor->az_g;
    g_motor_status.inference_count++;
}

static void task_inference(void *arg)
{
    (void)arg;

    static float raw_window[WINDOW_SIZE][N_CHANNELS];
    static int8_t quantized[WINDOW_SIZE * N_CHANNELS];

    int  sample_idx     = 0;
    bool window_filled  = false;
    int  stride_counter = 0;

    float probs[N_CLASSES];
    int   pred = 0;
    char  line[128];
    mpu6050_scaled_data_t sensor;
    TickType_t last_wake = xTaskGetTickCount();

    ESP_LOGI(TAG, "Inference: window=%d stride=%d period=%dms",
             WINDOW_SIZE, STRIDE_SIZE, SAMPLE_PERIOD_MS);

    while (1) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(SAMPLE_PERIOD_MS));

        if (mpu6050_read_scaled(&sensor) != ESP_OK)
            continue;

        raw_window[sample_idx][0] = sensor.ax_g;
        raw_window[sample_idx][1] = sensor.ay_g;
        raw_window[sample_idx][2] = sensor.az_g;
        sample_idx++;
        stride_counter++;

        if (!window_filled) {
            if (sample_idx < WINDOW_SIZE)
                continue;
            window_filled = true;
            sample_idx = 0;

            preprocess_window(raw_window, quantized);
            if (model_inference_run(quantized, probs, &pred) == ESP_OK) {
                led_set_class(pred);
                update_status(pred, probs, &sensor);
                int n = snprintf(line, sizeof(line),
                    "PREDICT:%s,%.4f,%.4f,%.4f\r\n",
                    CLASS_NAMES[pred], probs[0], probs[1], probs[2]);
                if (n > 0) uart_write_bytes(PC_UART_NUM, line, n);
                ESP_LOGI(TAG, ">> %s [%.1f%%, %.1f%%, %.1f%%]",
                         CLASS_NAMES[pred],
                         probs[0]*100, probs[1]*100, probs[2]*100);
            }
            stride_counter = 0;
            continue;
        }

        if (sample_idx >= WINDOW_SIZE)
            sample_idx = 0;

        if (stride_counter >= STRIDE_SIZE) {
            static float ordered[WINDOW_SIZE][N_CHANNELS];
            for (int i = 0; i < WINDOW_SIZE; i++) {
                int src = (sample_idx + i) % WINDOW_SIZE;
                ordered[i][0] = raw_window[src][0];
                ordered[i][1] = raw_window[src][1];
                ordered[i][2] = raw_window[src][2];
            }

            preprocess_window(ordered, quantized);
            if (model_inference_run(quantized, probs, &pred) == ESP_OK) {
                led_set_class(pred);
                update_status(pred, probs, &sensor);
                int n = snprintf(line, sizeof(line),
                    "PREDICT:%s,%.4f,%.4f,%.4f\r\n",
                    CLASS_NAMES[pred], probs[0], probs[1], probs[2]);
                if (n > 0) uart_write_bytes(PC_UART_NUM, line, n);
                ESP_LOGI(TAG, ">> %s [%.1f%%, %.1f%%, %.1f%%]",
                         CLASS_NAMES[pred],
                         probs[0]*100, probs[1]*100, probs[2]*100);
            }
            stride_counter = 0;
        }
    }
}


void app_main(void)
{
    led_init();
    pc_uart_init();
    i2c_master_init();
    mpu_init();

    wifi_init_softap();
    start_webserver();

    esp_err_t ret = model_inference_init();
    if (ret != ESP_OK)
        ESP_LOGE(TAG, "Model init FAILED");

    const char *banner =
        "\r\n"
        "======================================\r\n"
        "  Motor Fault Detection v1.0\r\n"
        "  1D-CNN INT8 | 3 classes\r\n"
        "  Window: 200 @ 100Hz (2.0s)\r\n"
        "  Stride: 50 (0.5s)\r\n"
        "  Dashboard: http://192.168.4.1\r\n"
        "======================================\r\n\r\n";
    uart_write_bytes(PC_UART_NUM, banner, strlen(banner));

    if (ret == ESP_OK)
        xTaskCreate(task_inference, "infer", 8192, NULL, 5, NULL);

    ESP_LOGI(TAG, "System ready");
}