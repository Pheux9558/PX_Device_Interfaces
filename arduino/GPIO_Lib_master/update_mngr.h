#include "oled.h"

// MOVE TO PIN DEF FILE //

// #define SD_MOSI     7
// #define SD_MISO     19
// #define SD_SCLK     18
// #define SD_CS       6

// #define SD_MOSI     5
// #define SD_MISO     15
// #define SD_SCLK     7
// #define SD_CS       6

// #################### //


#include <Update.h>
#include "SPI.h"
#include "SD.h"

#define non_rename_overwrite 1
int steps = 0;

void progressCallBack(size_t currSize, size_t totalSize) {
  //Serial.printf("CALLBACK:  Update process at %d of %d bytes...\n", currSize, totalSize);
  oled_progress("FW Update:," + String(currSize) + "/" + String(totalSize), false, steps);
  steps++;
}

void fw_update() {
  pinMode(non_rename_overwrite, INPUT_PULLUP);
  bool rename = digitalRead(non_rename_overwrite);
  
  delay(1000);
  oled_print_center_dynamic("INIT FW Update,from SD Card", true);

  File firmware =  SD.open("/firmware.bin");
  if (firmware) {
    Serial.println(F("File found"));
    oled_print_center_dynamic("INIT FW Update,from SD Card,File found", true);
  	delay(1000);
    Update.onProgress(progressCallBack);
    Update.begin(firmware.size(), U_FLASH);
    Update.writeStream(firmware);
    if (Update.end()){
      oled_print_center("Update finished!", true);
    }else{
      oled_print_center_dynamic("Update error!," + String(Update.getError()));
      return;
    }
    
    firmware.close();
    delay(1000);

    if (rename) {
      oled_print_center_dynamic("Firmware rename,firmware.bak");
      if (SD.rename("/firmware.bin", "/firmware.bak")){
        oled_print_center_dynamic("Firmware rename:,succesfully");
      }else{
        oled_print_center_dynamic("Firmware rename:,error");
      }
    }else {
      oled_print_center_dynamic("Firmware rename:,NOT_RN_OVERWRITE");
    }


    delay(1000);
    oled_print_center_dynamic("Restart ESP,.");
    delay(200);
    oled_print_center_dynamic("Restart ESP,..");
    delay(200);
    oled_print_center_dynamic("Restart ESP,...");
    delay(200);
    ESP.restart();

  }else{
    oled_print_center_dynamic("FW Update,no file found", true);
  }
}
