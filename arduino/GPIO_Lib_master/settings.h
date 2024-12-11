// !!! FIRMWARE need to be set !!!  (GPIO_lib_uno/GPIO_lib_mega)
#define FIRMWARE "GPIO_lib_mega"
#define MAX_BUF 64
#define BAUD 115200
//#define analog_start_pin 14

char buffer[MAX_BUF]; // where we store the message until we get a ';'
int sofar; // how much is in the buffer
int msg_from_port=0;
bool use_update = true; // use pin update function
int update_val = 0;  // carry for update
unsigned long previousMillis = 0;
const long interval = 10;
#define analog_tolerance 10
//LiquidCrystal_I2C lcd(0x27, 20, 4, 3, 4);
//LiquidCrystal_I2C lcd(0x27, 20, 4);















// Feature setup
#define displayOled true
#define powerSystem true
#define en_servo false


// define hardware
#define Processor esp32_s3_wroom01
// #define Processor esp32_pico_D4



// ##########PINOUT##########

  #define LED_DEBUG   2
  #define vibMotor    1

  #define SD_MOSI     5
  #define SD_MISO     15
  #define SD_SCLK     7
  #define SD_CS       6
  #define SD_DETECT   16

  #define triggerBtn  8
  #define batVoltage  9
  #define pwrOn       10

  #define OLED_SDA    41 
  #define OLED_SCL    42

// ##########################
#if displayOled
  #include "oled.h"
  PX_OLED_Lib OLED;

  void display_init() {
    OLED.oled_init(OLED_SDA, OLED_SCL);
  }

  void displayPrint(String text = "", bool color = false) {
    OLED.oled_print(text, color);
  }


  void display_print_center_dynamic(String text = "", bool color = false, bool show = true) {
    OLED.oled_print_center_dynamic(text, color, show);
  }


  void displaySetCursor(int x, int y) {
    OLED.oled_setCursor(x, y);
  }

  void displayClear() {
    OLED.oled_clear();
  }

  void display_progress(String text, bool color, float progress) {
    OLED.oled_progress(text, color, progress);
  }

  #else
  void display_init() {}
  void display_print_center_dynamic(String text = "", bool color = false, bool show = true) {}
  void displayPrint(String text = "") {}
  void displaySetCursor(int x, int y) {}
  void displayClear() {}
  void display_progress(String text, bool color, float progress) {}
#endif

#if powerSystem
  #define powerOffDelay 1000
  #define powerOfffHoldeTime 1500
  #include "powerSystem.h"
  PowerSystem power;
#endif


#define FIRMWARE_VERSION 1




#if Processor == esp32_s3_wroom01
#define serial1 true
#define serial2 false
#define serial3 false
#else
#define serial1 true
#define serial2 false
#define serial3 false
#endif





bool delayCustom(int time = 100) {
  for (int i = time; i > 0; i--) {
    if (Serial.available() > 0){
      while (Serial.available() > 0) {
        Serial.read();
      }
      Serial.println(">");
      // initBlock = false;
      return true;
    }
    delay(1);
  }
  return false;
}

bool ledRampUp(int ledPin, int time = 100) {
  for (int i = time; i > 0; i--) {
    int brightness = map(i, time, 0, 255, 0);
    analogWrite(ledPin, brightness);
    if (delayCustom(1)) {
      return false;
    }
  }
  return true;
}

bool ledRampDown(int ledPin, int time = 100) {
  for (int i = time; i > 0; i--) {
    int brightness = map(i, time, 0, 0, 255);
    analogWrite(ledPin, brightness);
    if (delayCustom(1)) {
      return false;
    }
  }
  return true;
}

























#if Processor == esp32_s3_wroom01
  void test() {

  }
#elif Processor == esp32_pico_D4

#endif


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