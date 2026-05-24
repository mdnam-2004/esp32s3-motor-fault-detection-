#include "pzem_004t.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char *TAG = "PZEM004T";
static uint16_t modbus_crc16(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFF;

    for (uint16_t i = 0; i < len; i++)
    {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++)
        {
            if (crc & 0x0001)
                crc = (crc >> 1) ^ 0xA001;
            else
                crc >>= 1;
        }
    }
    return crc;
}

static esp_err_t read_exact(uart_port_t uart,
                            uint8_t *buf,
                            size_t len,
                            uint32_t timeout_ms)
{
    size_t received = 0;
    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);

    while (received < len)
    {
        if (xTaskGetTickCount() > deadline)
            return ESP_ERR_TIMEOUT;

        int r = uart_read_bytes(uart,
                                buf + received,
                                len - received,
                                pdMS_TO_TICKS(20));

        if (r > 0)
            received += r;
    }

    return ESP_OK;
}

esp_err_t pzem_init(pzem_handle_t *h,
                    uart_port_t uart_num,
                    int tx_pin,
                    int rx_pin,
                    uint32_t baudrate,
                    uint8_t slave_addr,
                    uint32_t timeout_ms)
{
    if (!h)
        return ESP_ERR_INVALID_ARG;

    memset(h, 0, sizeof(*h));

    h->uart_num = uart_num;
    h->tx_pin = tx_pin;
    h->rx_pin = rx_pin;
    h->baudrate = baudrate ? baudrate : 9600;
    h->slave_addr = slave_addr;
    h->timeout_ms = timeout_ms ? timeout_ms : 1000;

    uart_config_t cfg = {
        .baud_rate = h->baudrate,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT
    };

    ESP_ERROR_CHECK(uart_param_config(h->uart_num, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(h->uart_num, tx_pin, rx_pin,
                                 UART_PIN_NO_CHANGE,
                                 UART_PIN_NO_CHANGE));

    ESP_ERROR_CHECK(uart_driver_install(h->uart_num,
                                        256,
                                        0,
                                        0,
                                        NULL,
                                        0));

    uart_flush_input(h->uart_num);

    ESP_LOGI(TAG, "UART%d init OK", h->uart_num);

    return ESP_OK;
}


esp_err_t pzem_read_current_a(pzem_handle_t *h, float *out_current)
{
    if (!h || !out_current)
        return ESP_ERR_INVALID_ARG;

    uint8_t req[8];

    req[0] = h->slave_addr;
    req[1] = 0x04;
    req[2] = 0x00;
    req[3] = 0x00;
    req[4] = 0x00;
    req[5] = 0x0A;

    uint16_t crc = modbus_crc16(req, 6);
    req[6] = crc & 0xFF;
    req[7] = (crc >> 8) & 0xFF;

    uart_flush_input(h->uart_num);

    uart_write_bytes(h->uart_num, (const char *)req, sizeof(req));
    uart_wait_tx_done(h->uart_num, pdMS_TO_TICKS(h->timeout_ms));

    uint8_t resp[25];

    esp_err_t err = read_exact(h->uart_num,
                               resp,
                               sizeof(resp),
                               h->timeout_ms);
    if (err != ESP_OK)
        return err;

    if (resp[0] != h->slave_addr ||
        resp[1] != 0x04 ||
        resp[2] != 20)
        return ESP_ERR_INVALID_RESPONSE;

    uint16_t crc_calc = modbus_crc16(resp, 23);
    uint16_t crc_rx   = resp[23] | (resp[24] << 8);

    if (crc_calc != crc_rx)
        return ESP_ERR_INVALID_CRC;

    uint16_t cur_low  = (resp[5] << 8) | resp[6];
    uint16_t cur_high = (resp[7] << 8) | resp[8];

    uint32_t raw = ((uint32_t)cur_high << 16) | cur_low;

    *out_current = raw * 0.001f;

    return ESP_OK;
}