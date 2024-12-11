#ifndef POWER_SYSTEM_LIB_H_
#define POWER_SYSTEM_LIB_H_

#include <Arduino.h>

/* ###############  PowerSystem ############### */
class PowerSystem {
    public: 
        PowerSystem();
        void setPowerPin(int pin);
        // void setButtonPin(uint16_t pin);
        void setTime(int time);
        void on();
        void off();
        void offTick();
    private:
        int powerPin;
        int powerOffTime;
        // uint8_t buttonPin;
};
#endif