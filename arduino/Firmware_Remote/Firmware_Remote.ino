

/*
2400 <> 4,15V
1740 <> 3,15V
1650 <> 3V

*/


// ##########PINOUT##########

#define LED_DEBUG   2
#define vibMotorr   1

#define SD_MOSI     5
#define SD_MISO     15
#define SD_SCLK     7
#define SD_CS       6
#define SD_DETECT   16

#define triggerBtn  8
#define batVoltage  9
#define pwrOn       10

#define OLED_SCL    42
#define OLED_SDA    41 

// ##########################
#define FIRMWARE_VERSION 3
#include "update_mngr.h"
String init_text;


#include "Flapp.h"


#define powerOffDelay 1000
#define powerOfffHoldeTime 200
bool pwrState = true;


void setup() {
  // put your setup code here, to run once:
  pinMode(triggerBtn, INPUT);
  pinMode(pwrOn, OUTPUT);
  pinMode(LED_DEBUG, OUTPUT);
  pinMode(vibMotorr, OUTPUT);
  digitalWrite(pwrOn, HIGH);
  digitalWrite(LED_DEBUG, HIGH);
  

  Serial.begin(115200);
  oled_init();
  oled_print_center_dynamic("Startup...");
  SPI.begin(SD_SCLK, SD_MISO, SD_MOSI, SD_CS);

  while(digitalRead(triggerBtn)) {}

  if (!SD.begin(SD_CS)) 
  {
    init_text += "SD Status: FAIL";
  }else {
    init_text += "SD Status: OK";
  }

  init_text += ",FW Version: "+ String(FIRMWARE_VERSION);
  

  int batAnalogValue = analogRead(batVoltage);
  int batVal = map(batAnalogValue, 1650, 2400, 300, 415);
  float batVoltageVal = (float)batVal / 100;
  oled_print_center_dynamic(init_text + ",Bat: " + String(batAnalogValue) + ",Bat Voltage: " + String(batVoltageVal) + "V");


  digitalWrite(LED_DEBUG, LOW);
  Serial.begin(115200);
}


int btn_tmr = 0;
bool btn_relese_flag = false;


int btn() {
  btn_relese_flag = false;

  if(digitalRead(triggerBtn)) {
    if (btn_tmr == 0) {
      delay(10);
    }
    btn_tmr++;

  }else {
    if(btn_tmr > 0) {
      btn_tmr = 0;
      btn_relese_flag = true;
    }
  }
  return btn_tmr;
}



void loop() {
  // put your main code here, to run repeatedly:
  delay(1);

  int btnPressTime = btn();

  if ((btnPressTime >= powerOffDelay) && 
      (powerOffDelay + powerOfffHoldeTime >= btnPressTime)
      ) {

    if (btnPressTime % (powerOfffHoldeTime / 10) == 0) {
      int val = map(btnPressTime, powerOffDelay, powerOffDelay + powerOfffHoldeTime, 0, 100);
      oled_progress("Hold Button,for Power down", false, val);
    }
    if (btnPressTime == powerOffDelay + powerOfffHoldeTime) {
    oled_print_center_dynamic("Relese Button,for Power Down");
    digitalWrite(pwrOn, LOW);
    
    pwrState = false;
    }
  }

  if (btn_relese_flag && pwrState) {
    digitalWrite(vibMotorr, HIGH);
    digitalWrite(LED_DEBUG, HIGH);
    delay(250);
    digitalWrite(vibMotorr, LOW);
    digitalWrite(LED_DEBUG, LOW);

    flapp_start();

    int batAnalogValue = analogRead(batVoltage);
    int batVal = map(batAnalogValue, 1650, 2400, 300, 415);
    float batVoltageVal = (float)batVal / 100;
    oled_print_center_dynamic(init_text + ",Bat: " + String(batAnalogValue) + ",Bat Voltage: " + String(batVoltageVal) + "V");

  }

}




