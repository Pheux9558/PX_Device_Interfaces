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

#include "serial_rtos.h"
  #include "serial.h"
#include "cmd.h"
#include "dispatch.h"
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
#if defined(ENCODER_SUPPORT)
#include "encoder.h"
#endif
#if defined(STEPPER_SUPPORT)
#include "stepper.h"
#endif
#if defined(ARDUINO_UNOR4_WIFI)
#include "matrix.h"
#endif
#if defined(DEBUG)
#include "debug.h"
#endif
#include "board.h"
#include <string.h>
#include <stdio.h>

// Simple main that initializes subsystems and enters FreeRTOS task loop

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
  // Initialize FreeRTOS-based serial transport
  // This creates RxTask (serial reader) and TxTask (serial writer)
  serial_rtos_begin(921600);
  
  // Give USB CDC a moment to enumerate on some boards (ESP32-S3, Pico etc.)
  delay(100);
  const char *serial_msg = "serial_rtos: initialized at 921600 baud\n";
  serial_write((const uint8_t *)serial_msg, strlen(serial_msg));
  
  // initialize modules registry first so module init() calls can register flags
  modules_init();

  firmware_init();

  // initialize board module so it can register board-specific flags
  const char *board_msg = "board: initializing board module\n";
  serial_write((const uint8_t *)board_msg, strlen(board_msg));
  board_init();

  // initialize GPIO module
  const char *gpio_msg = "gpio: initializing gpio module\n";
  serial_write((const uint8_t *)gpio_msg, strlen(gpio_msg));
  gpio_init();

  // initialize FastLED module (register flags)
#if defined(FASTLED_SUPPORT)
  const char *fastled_msg = "fastled: initializing fastled module\n";
  serial_write((const uint8_t *)fastled_msg, strlen(fastled_msg));
  fastled_init();
#endif

#if defined(UART_SUPPORT)
  const char *uart_msg = "uart: initializing uart module\n";
  serial_write((const uint8_t *)uart_msg, strlen(uart_msg));
  gpio_uart_init();
#endif

#if defined(I2C_SUPPORT)
  const char *i2c_msg = "i2c: initializing i2c module\n";
  serial_write((const uint8_t *)i2c_msg, strlen(i2c_msg));
  i2c_init();
#endif

#if defined(SPI_SUPPORT)
  const char *spi_msg = "spi: initializing spi module\n";
  serial_write((const uint8_t *)spi_msg, strlen(spi_msg));
  spi_init();
#endif

#if defined(LCD_SUPPORT) || defined(HD44780_SUPPORT) || defined(AIP31068L_SUPPORT)
  const char *lcd_msg = "lcd: initializing lcd module\n";
  serial_write((const uint8_t *)lcd_msg, strlen(lcd_msg));
  lcd_init();
#endif

#if defined(OLED_SUPPORT)
  const char *oled_msg = "oled: initializing oled module\n";
  serial_write((const uint8_t *)oled_msg, strlen(oled_msg));
  oled_init();
#endif

#if defined(ENCODER_SUPPORT)
  const char *encoder_msg = "encoder: initializing encoder module\n";
  serial_write((const uint8_t *)encoder_msg, strlen(encoder_msg));
  encoder_init();
#endif

#if defined(STEPPER_SUPPORT)
  const char *stepper_msg = "stepper: initializing stepper module\n";
  serial_write((const uint8_t *)stepper_msg, strlen(stepper_msg));
  stepper_init();
#endif

#if defined(ARDUINO_UNOR4_WIFI)
  const char *matrix_msg = "matrix: initializing una r4 matrix module\n";
  serial_write((const uint8_t *)matrix_msg, strlen(matrix_msg));
  matrix_init();
#endif

#if defined(DEBUG)
  const char *debug_msg = "debug: initializing debug module\n";
  serial_write((const uint8_t *)debug_msg, strlen(debug_msg));
  debug_init();
#endif

  // Initialize command dispatcher.
  // All service handlers are self-registered via CMD_REGISTER() in each
  // service file; cmd_init() calls cmd_auto_register_all() to apply them.
  dispatch_init();
  cmd_init();

  // send a ready banner so host can handshake and avoid race with bootloader
  const char *ready = "GPIO_READY\r\n";
  serial_write((const uint8_t *)ready, (size_t)strlen(ready));
}

void loop() {
  // Non-blocking debug heartbeat LED
#if defined(DEBUG)
  debug_heartbeat();
#endif

  // Detect USB CDC reconnection and resend ready banner
  #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_ARCH_STM32)
  static bool was_connected = false;
  bool is_connected = Serial;  // Serial evaluates to true when USB CDC is connected
  
  if (is_connected && !was_connected) {
    // USB CDC just reconnected - resend ready banner
    const char *ready = "GPIO_READY\r\n";
    serial_write((const uint8_t *)ready, (size_t)strlen(ready));
  }
  was_connected = is_connected;
  #endif

  // Dispatch one packet from RxTask's cmd_queue (non-blocking)
  dispatch_packet();

  // Poll GPIO inputs (will become GpioTask in Phase 2)
  gpio_poll_inputs();

#if defined(ARDUINO_UNOR4_WIFI)
  // Update custom matrix animations
  matrix_update();
#endif

  #if defined(ENCODER_SUPPORT)
    encoder_poll();
  #endif

  #if defined(STEPPER_SUPPORT)
    stepper_poll();
  #endif

  // Minimal delay to let other FreeRTOS tasks run
  // RxTask and TxTask will handle serial I/O asynchronously
  // Once Phase 2 ports FreeRTOS properly, this becomes rtosal_delay_ms(10)
  delay(2);
}
#endif
