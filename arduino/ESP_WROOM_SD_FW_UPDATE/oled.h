
#include <SparkFun_Qwiic_OLED.h>
QwiicTransparentOLED OLED;


// MOVE TO PIN DEF FILE //

//#define OLED_SCL 4
//#define OLED_SDA 5

#define OLED_SCL 42
#define OLED_SDA 40

// #################### //

void oled_init() {
  Wire.begin(OLED_SDA, OLED_SCL);
  OLED.begin(Wire);
}

void oled_edge(bool color = false) {
  OLED.rectangleFill(0, 0, OLED.getWidth(), OLED.getHeight(), !color);
  OLED.rectangleFill(4, 4, OLED.getWidth() - 8, OLED.getHeight() - 8, color);
  OLED.rectangle(0, 0, OLED.getWidth(), OLED.getHeight(), color);
}

void oled_print_center_dynamic(String text = "", bool color = false, bool show = true) {
  OLED.erase();
  oled_edge(color);

  int y0 = 10;
  int index = 0;
  String sub_string = "";

  while (index >= 0) {
    index = text.indexOf(",");
    sub_string = text.substring(0, index);
    int x0 = (OLED.getWidth() - OLED.getStringWidth(sub_string)) / 2;
    OLED.text(x0, y0, sub_string, !color);
    y0 += OLED.getStringHeight(sub_string) + 3;
    text.remove(0, index + 1);
  }
  if (show){
    OLED.display();
  }
}

void oled_print_center(String text = "", bool color = false) {
  OLED.erase();
  oled_edge(color);

  int x = (OLED.getWidth() - OLED.getStringWidth(text)) / 2;
  int y = (OLED.getHeight() - OLED.getStringHeight(text)) / 2;
  OLED.text(x, y, text, !color);
  OLED.display();
}


void oled_progress(String text = "", bool color = false, float progress = 0) {
  oled_print_center_dynamic(text, color, false);

  int progress_wight = 1;
  if(progress > 0) {
    float procentage = progress / 100;
    progress_wight = (OLED.getWidth() - 50) * procentage;
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
 
  OLED.rectangleFill(10, OLED.getHeight() - 20, OLED.getWidth() - 50, 10, color);
  OLED.rectangle(10, OLED.getHeight() - 20, OLED.getWidth() - 50, 10, !color);
  OLED.rectangleFill(10, OLED.getHeight() - 20, progress_wight, 10, !color);
  OLED.text(OLED.getWidth() - 35, OLED.getHeight() - 19, load_text, !color);
  OLED.display();

}
