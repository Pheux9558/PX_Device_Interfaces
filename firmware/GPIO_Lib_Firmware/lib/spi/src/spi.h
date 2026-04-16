// SPI Service (Phase 4 bootstrap)
// Provides command handling for SPI create/config/read/write.
// Task ownership can be added later without changing command semantics.
#pragma once

#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>

#if defined(ARDUINO)
#include <SPI.h>
#endif

void spi_init(void);
bool spi_cmd_handler(uint16_t cmd, const uint8_t *payload, uint16_t len);
const char *spi_module_flags(void);

#if defined(ARDUINO)
typedef struct {
	uint16_t id;
	SPIClass *spi;
	int8_t sck;
	int8_t mosi;
	int8_t miso;
	uint32_t freq;
	uint8_t mode;
	bool used;
} gpio_lib_spi_instance_t;

gpio_lib_spi_instance_t *spi_get_instance(uint16_t id);
#endif
