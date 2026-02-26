#include <Arduino.h>
#if defined(RESET_DEVICE_SUPPORT)
void setup() {
  // clear controller from firmware. Deleding firmware from flash will cause the device to be unresponsive until reprogrammed

}
void loop() {
  // do nothing
  delay(1000);
}
#else

#define BUFFER_SIZE 2048


#include "serial.h"
#include "cmd.h"
#include "gpio.h"
#include "firmware.h"
#include "modules.h"
#if defined(FASTLED_SUPPORT)
#include "fastled.h"
#endif
#if defined(UART_SUPPORT)
#include "uart.h"
#endif
#if defined(I2C_SUPPORT)
#include "i2c.h"
#endif
#if defined(SPI_SUPPORT)
#include "spi.h"
#endif
#if defined(LCD_SUPPORT) || defined(HD44780_SUPPORT) || defined(AIP31068L_SUPPORT)
#include "lcd.h"
#endif
#if defined(OLED_SUPPORT)
#include "oled.h"
#endif
#if defined(DEBUG)
#include "debug.h"
#endif
#include "board.h"
#include <string.h>
#include <stdio.h>

u_int32_t millis_last_cmd = 0;

// Simple main that initializes subsystems and echoes valid packets

#if defined(DEBUG)
// forward GPIO debug callbacks to serial for visibility
static void debug_to_serial(const char *msg) {
  if (!msg) return;
  serial_write((const uint8_t *)msg, strlen(msg));
  const uint8_t nl[2] = {'\r', '\n'};
  serial_write(nl, 2);
}

#endif

void setup() {
  serial_begin(921600);
  // Give USB CDC a moment to enumerate on some boards (ESP32-S3, Pico etc.)
  delay(100);
  serial_write((const uint8_t *)"serial: initialized at 921600 baud\n", 35);
  
  // initialize modules registry first so module init() calls can register flags
  modules_init();

  // initialize board module so it can register board-specific flags
  serial_write((const uint8_t *)"board: initializing board module\n", 33);
  board_init();

  // initialize GPIO module
  serial_write((const uint8_t *)"gpio: initializing gpio module\n", 31);
  gpio_init();

  // initialize FastLED module (register flags)
#if defined(FASTLED_SUPPORT)
  serial_write((const uint8_t *)"fastled: initializing fastled module\n", 37);
  fastled_init();
#endif

#if defined(UART_SUPPORT)
  serial_write((const uint8_t *)"uart: initializing uart module\n", 34);
  uart_init();
#endif

#if defined(I2C_SUPPORT)
  serial_write((const uint8_t *)"i2c: initializing i2c module\n", 32);
  i2c_init();
#endif

#if defined(SPI_SUPPORT)
  serial_write((const uint8_t *)"spi: initializing spi module\n", 32);
  spi_init();
#endif

#if defined(LCD_SUPPORT) || defined(HD44780_SUPPORT) || defined(AIP31068L_SUPPORT)
  serial_write((const uint8_t *)"lcd: initializing lcd module\n", 32);
  lcd_init();
#endif

#if defined(OLED_SUPPORT)
  serial_write((const uint8_t *)"oled: initializing oled module\n", 33);
  oled_init();
#endif

#if defined(DEBUG)
  serial_write((const uint8_t *)"debug: initializing debug module\n", 34);
  debug_init();
#endif

  // Initialize command dispatcher and register module handlers
  cmd_init();
  cmd_register_handler(0x0000, 0x001F, gpio_cmd_handler); // gpio setup & similar
  
#if defined(FASTLED_SUPPORT)
  cmd_register_handler(0x0110, 0x012F, fastled_cmd_handler);    // FastLED control
#endif
#if defined(UART_SUPPORT)
  cmd_register_handler(0x0200, 0x020F, uart_cmd_handler);       // UART control
#endif
#if defined(I2C_SUPPORT)
  cmd_register_handler(0x0210, 0x021F, i2c_cmd_handler);        // I2C control
#endif
#if defined(SPI_SUPPORT)
  cmd_register_handler(0x0220, 0x022F, spi_cmd_handler);        // SPI control
#endif
#if defined(LCD_SUPPORT)
  cmd_register_handler(0x0020, 0x002F, st7735_cmd_handler);     // ST7735 control
#endif
#if defined(HD44780_SUPPORT)
  cmd_register_handler(0x0030, 0x003F, hd44780_cmd_handler);    // HD44780 control
#endif
#if defined(AIP31068L_SUPPORT)
  cmd_register_handler(0x0040, 0x004F, aip31068l_cmd_handler);  // AiP31068L control
#endif
#if defined(OLED_SUPPORT)
  cmd_register_handler(0x0050, 0x005F, ssd1306_cmd_handler);    // SSD1306 control
#endif
  cmd_register_handler(0xFFFC, 0xFFFF, firmware_cmd_handler);   // firmware-level cmds like reset, firmware feedback, etc.

  // send a ready banner so host can handshake and avoid race with bootloader
  const char *ready = "GPIO_READY\r\n";
  serial_write((const uint8_t *)ready, (size_t)strlen(ready));
}


static uint8_t checksum_for(uint16_t cmd, uint16_t len, const uint8_t *payload) {
  uint32_t sum = cmd + len;
  for (uint16_t i = 0; i < len; ++i) sum += payload[i];
  return (uint8_t)(sum & 0xFF);
}

int calc_delay() {
  // simple heuristic: if we've gone a long time since last command, delay more to save power
  if (millis() - millis_last_cmd < 50) return 0;
  if (millis() - millis_last_cmd < 100) return 5;
  if (millis() - millis_last_cmd < 500) return 10;
  if (millis() - millis_last_cmd < 1000) return 50;
  if (millis() - millis_last_cmd < 2500) return 100;
  if (millis() - millis_last_cmd < 5000) return 250;
  if (millis() - millis_last_cmd < 10000) return 500;
  return 1000;
}

void loop() {
  // Non-blocking debug heartbeat LED
#if defined(DEBUG)
  debug_heartbeat();
#endif

  // read bytes from serial and pass them to the command dispatcher
  if (serial_available() > 0) {
    uint8_t inbuf[BUFFER_SIZE];
    size_t idx = 0;
    while (serial_available() > 0 && idx < sizeof(inbuf)) {
      int c = serial_read();
      if (c < 0) break;
      inbuf[idx++] = (uint8_t)c;
    }
    if (idx) {
      millis_last_cmd = millis();
      cmd_process_bytes(inbuf, idx);
    }
  }


  gpio_poll_inputs();

  // replace with dynamic delay based on activity
  delay(calc_delay());
}
#endif
