#if defined(STM32F1) || defined(STM32F4) || defined(ARDUINO_ARCH_STM32)

/*
 * STM32 HAL port placeholder.
 *
 * Concrete GPIO/UART/I2C/SPI bindings will be added incrementally in
 * service migration phases.
 */

const char *hal_port_name_stm32(void) {
    return "stm32";
}

#endif
