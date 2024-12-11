#ifndef pxOLED_LIB_H_
#define pxOLED_LIB_H_


#include <SparkFun_Qwiic_OLED.h>




/* ###############  PX_OLED_Lib ############### */
class PX_OLED_Lib {
    public: 
        PX_OLED_Lib();
        void oled_init(int SDA, int SCL);
        void oled_edge(bool color);
        void oled_print_center_dynamic(String text, bool color, bool show);
        void oled_print_center(String text, bool color);
        void oled_print(String text, bool color);
        void oled_progress(String text, bool color, float progress);
        void oled_clear();
        void oled_setCursor(int x, int y);
    private:
        int x_pos;
        int y_pos;
        // uint8_t buttonPin;
};

// #################### //

/* #################  pxOLED_LIB_H_ ################ 
....
....
....
*/
#endif
