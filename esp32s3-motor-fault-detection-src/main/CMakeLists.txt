idf_component_register(SRCS "fault_motor_main.c" "model_inference.cc" "web_server.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES pzem_004t driver mpu_6050 esp_timer
                                     esp_wifi esp_http_server esp_netif esp_event nvs_flash
                       EMBED_FILES "model/motor_fault_int8.tflite"
                       )
