#pragma once

// Some ESP32 toolchains define SPI as a macro on the command line.
// This breaks Arduino's SPIClass declaration. Undefine it early.
#ifdef SPI
#undef SPI
#endif
