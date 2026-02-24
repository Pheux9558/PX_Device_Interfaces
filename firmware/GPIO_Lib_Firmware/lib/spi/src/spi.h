#pragma once
#include <stdint.h>
#include <stdbool.h>

#if defined(ARDUINO)
#include <SPI.h>
#endif

void spi_init();
bool spi_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *spi_module_flags();

#if defined(ARDUINO)
struct gpio_lib_spi_instance_t {
    uint16_t id;
    SPIClass *spi;
    int8_t sck;
    int8_t mosi;
    int8_t miso;
    uint32_t freq;
    uint8_t mode;
    bool used;
};

gpio_lib_spi_instance_t *spi_get_instance(uint16_t id);
#endif
