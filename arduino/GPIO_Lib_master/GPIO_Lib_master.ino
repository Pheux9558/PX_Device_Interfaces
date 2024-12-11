//#include <LiquidCrystal_I2C.h>
#include <Wire.h>

#include "settings.h"
#include "gpio_lib_commands.h"
String init_text;


// ############ Trigger Button ###############
  void triggerButton() {
    digitalWrite(vibMotor, HIGH);
    digitalWrite(LED_DEBUG, HIGH);
    delay(250);
    digitalWrite(vibMotor, LOW);
    digitalWrite(LED_DEBUG, LOW);

    int batAnalogValue = analogRead(batVoltage);
    int batVal = map(batAnalogValue, 1650, 2400, 300, 415);
    float batVoltageVal = (float)batVal / 100;
    display_print_center_dynamic(init_text + ",Bat: " + String(batAnalogValue) + ",Bat Voltage: " + String(batVoltageVal) + "V");
  }

// ###########################################


// ############# TEMP POWER SYS ##############
  bool pwrState = true;
  unsigned long btn_tmr = 0;
  unsigned long lastMillis = 0;
  bool btn_relese_flag = false;

  unsigned long btn() {
    btn_relese_flag = false;

    if (digitalRead(triggerBtn)) {
      if (btn_tmr == 0) {
        lastMillis = millis();
      }
      btn_tmr = millis() - lastMillis;

    } else {
      if (btn_tmr > 0) {
        btn_tmr = 0;
        lastMillis = 0;
        btn_relese_flag = true;
      }
    }
    return btn_tmr;
  }


  void shutdownFunction() {
    unsigned long btnPressTime = btn();
    //serialPrintln(String(btnPressTime));

    if ((btnPressTime >= powerOffDelay) && (powerOffDelay + powerOfffHoldeTime >= btnPressTime)) {

      //if (btnPressTime % (powerOfffHoldeTime / 10) == 0) {
        int val = map(btnPressTime, powerOffDelay, powerOffDelay + powerOfffHoldeTime, 0, 100);
        display_progress("Hold Button,for Power down", false, val);
    }
    if (btnPressTime >= powerOffDelay + powerOfffHoldeTime) {
      display_print_center_dynamic("Relese Button,for Power Down");
      #if powerSystem
      power.off();
      #endif
      pwrState = false;
    }

    if (btn_relese_flag && pwrState) {
      triggerButton();
    }
  }
// ###########################################

void setup() {
  // put your setup code here, to run once:
  serialBegin(BAUD);
  init_text += "Starting GPIO_lib";
  init_text += ",FW Version: " + String(FIRMWARE_VERSION);
  #if powerSystem
    power.setPowerPin(pwrOn);
    pinMode(triggerBtn, INPUT);
    power.setTime(100);
    init_text += ",Power System Active";
    Serial.println("Power System Active");
    #else
    Serial.println("Power System Inactive");
  #endif

  pinMode(LED_DEBUG, OUTPUT);
  pinMode(vibMotor, OUTPUT);
  digitalWrite(LED_DEBUG, HIGH);

  init_text += ",SD Card: Fail";
  Serial.println("SD Card: Fail");

  display_init();
  display_print_center_dynamic(init_text);
  sofar = 0;
  for (int i = 0; i < io_pins; i++) {
    input_array[i][1] = 0;
  }


  while(digitalRead(triggerBtn)) {}


  serialPrintln(">");

  digitalWrite(LED_DEBUG, LOW);
}


void loop() {
  gpio_lib_loop();
  shutdownFunction();
}
