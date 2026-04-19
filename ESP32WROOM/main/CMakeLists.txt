# Main component CMakeLists.txt
# This file configures the main component for the ESP32 project

idf_component_register(
    SRCS
        "main.c"
        "wifi_manager.c"
        "uart_manager.c"
        "mqtt_listener.c"
        "action_functions.c"
        "mqtt_ota_handler.c"
        "alarm_manager.c"
    INCLUDE_DIRS
        "."
    REQUIRES
        esp_wifi
        nvs_flash
        esp_event
        mqtt
        app_update
        esp_http_client
        json
        driver
        mbedtls
)