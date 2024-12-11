#include <Arduino.h>
#include "oled.h"

QwiicTransparentOLED PX_OLED;


PX_OLED_Lib::PX_OLED_Lib() {
  x_pos = 0;
  y_pos = 0;
}

void PX_OLED_Lib::oled_init(int SDA, int SCL) {
  Wire.begin(SDA, SCL);
  PX_OLED.begin(Wire);
}

void PX_OLED_Lib::oled_edge(bool color = false) {
  int wallWidth = 2;
  PX_OLED.rectangleFill(0, 0, PX_OLED.getWidth(), wallWidth, !color);
  PX_OLED.rectangleFill(0, 0, wallWidth, PX_OLED.getHeight(), !color);
  PX_OLED.rectangleFill(0, PX_OLED.getHeight() -wallWidth, PX_OLED.getWidth(), wallWidth, !color);
  PX_OLED.rectangleFill(PX_OLED.getWidth() - wallWidth, 0, wallWidth, PX_OLED.getHeight(), !color);
}

void PX_OLED_Lib::oled_print_center_dynamic(String text = "", bool color = false, bool show = true) {
  PX_OLED.erase();
  oled_edge(color);

  int y0 = 10;
  int index = 0;
  String sub_string = "";

  while (index >= 0) {
    index = text.indexOf(",");
    sub_string = text.substring(0, index);
    int x0 = (PX_OLED.getWidth() - PX_OLED.getStringWidth(sub_string)) / 2;
    PX_OLED.text(x0, y0, sub_string, !color);
    y0 += PX_OLED.getStringHeight(sub_string) + 3;
    text.remove(0, index + 1);
  }
  if (show){
    PX_OLED.display();
  }
}

void PX_OLED_Lib::oled_print_center(String text = "", bool color = false) {
  PX_OLED.erase();
  oled_edge(color);

  int x = (PX_OLED.getWidth() - PX_OLED.getStringWidth(text)) / 2;
  int y = (PX_OLED.getHeight() - PX_OLED.getStringHeight(text)) / 2;
  PX_OLED.text(x, y, text, !color);
  PX_OLED.display();
}


void PX_OLED_Lib::oled_print(String text = "", bool color = false) {
  oled_edge(color);

  PX_OLED.text(x_pos, y_pos, text, !color);
  PX_OLED.display();
}

void PX_OLED_Lib::oled_setCursor(int x = 0, int y = 0) {
  x_pos = x;
  y_pos = y;
}


void PX_OLED_Lib::oled_clear() {
  PX_OLED.erase();
  PX_OLED.display();
  oled_setCursor();
}


void PX_OLED_Lib::oled_progress(String text = "", bool color = false, float progress = 0) {
  oled_print_center_dynamic(text, color, false);

  int progress_wight = 1;
  if(progress > 0) {
    float procentage = progress / 100;
    progress_wight = (PX_OLED.getWidth() - 50) * procentage;
  }

  String load_text = "ERR%";

  switch (int(progress)){
    case 0:
       load_text = "  0%";
      break;
    case 1 ... 9:
       load_text = "  " + String(int(progress)) + "%";
      break;
    case 10 ... 99:
       load_text = " " + String(int(progress)) + "%";
      break;
    case 100:
       load_text = "100%";
      break;
  }
 
  PX_OLED.rectangleFill(10, PX_OLED.getHeight() - 20, PX_OLED.getWidth() - 50, 10, color);
  PX_OLED.rectangle(10, PX_OLED.getHeight() - 20, PX_OLED.getWidth() - 50, 10, !color);
  PX_OLED.rectangleFill(10, PX_OLED.getHeight() - 20, progress_wight, 10, !color);
  PX_OLED.text(PX_OLED.getWidth() - 35, PX_OLED.getHeight() - 19, load_text, !color);
  PX_OLED.display();

}
