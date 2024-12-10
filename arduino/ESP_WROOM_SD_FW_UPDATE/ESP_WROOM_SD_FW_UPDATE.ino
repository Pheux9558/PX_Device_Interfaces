

#include "update_mngr.h"


#define FIRMWARE_VERSION 3
#define btn 48
#define LED 10
String init_text;

void setup() {
  Serial.begin(115200);
  oled_init();
  SPI.begin(SD_SCLK, SD_MISO, SD_MOSI, SD_CS);


  pinMode(btn, INPUT_PULLUP);
  pinMode(LED, OUTPUT);


  if (!SD.begin(SD_CS)) 
  {
    init_text += "SD Status: FAIL";
  }else {
    init_text += "SD Status: OK";
  }

  init_text += ",FW Version: "+ String(FIRMWARE_VERSION);

  oled_print_center_dynamic(init_text);

  if (digitalRead(btn) == LOW) {
    fw_update();
  }


  delay(1000);
}


#if FIRMWARE_VERSION == 1
  void loop() {
    digitalWrite(LED, HIGH);  // turn the LED on (HIGH is the voltage level)
    oled_print_center_dynamic("HELLO,LINE 2,3");
    delay(1000);                      // wait for a second
    digitalWrite(LED, LOW);   // turn the LED off by making the voltage LOW
    oled_print_center_dynamic("AAAAA,BBBB,CCCC");
    delay(1000);
  }
#endif

#if FIRMWARE_VERSION == 2
  void loop() {
    digitalWrite(LED, HIGH);  // turn the LED on (HIGH is the voltage level)
    delay(100);                      // wait for a second
    digitalWrite(LED, LOW);   // turn the LED off by making the voltage LOW
    delay(200);
    digitalWrite(LED, HIGH);  // turn the LED on (HIGH is the voltage level)
    delay(100);                      // wait for a second
    digitalWrite(LED, LOW);   // turn the LED off by making the voltage LOW
    delay(600);
  }
#endif

#if FIRMWARE_VERSION == 3

  void loop() {
    for(int i = 0; i <= 100; i++) {
      oled_progress(init_text + ",Count up", false, i);
    }

    for(int i = 100; i > 1; i--) {
      oled_progress(init_text + ",Count down", false, i);
    }
    
  }

#endif

