#pragma once

#include <stdint.h>
#include "driver/uart.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    uart_port_t uart_num;
    int tx_pin;
    int rx_pin;
    uint32_t baudrate;
    uint8_t slave_addr;
    uint32_t timeout_ms;
} pzem_handle_t;

esp_err_t pzem_init(pzem_handle_t *h,
                    uart_port_t uart_num,
                    int tx_pin,
                    int rx_pin,
                    uint32_t baudrate,
                    uint8_t slave_addr,
                    uint32_t timeout_ms);

esp_err_t pzem_read_current_a(pzem_handle_t *h, float *out_current);

#ifdef __cplusplus
}
#endif