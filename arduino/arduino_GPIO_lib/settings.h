#define arduino_mega

#ifdef arduino_mega
  #define io_pins 70

#endif

int input_array[io_pins][2]; // list to check pin update
/*  __________________|
   |   what dose those vals mean?
   v
  [0] Mode: 0 == Ignored in update, 1 == Digital_read, 2 == Analog_read
  [1] Val: Digital 0/1, Analog 0-1024
*/

void set_input_array(int mode, int pin) {
  input_array[pin][0] = mode;
}