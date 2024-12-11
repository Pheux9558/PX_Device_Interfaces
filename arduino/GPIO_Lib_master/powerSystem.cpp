#include <Arduino.h>
#include "powerSystem.h"

/* ###############  PowerSystem ############### */

/************  Constructor ************/

PowerSystem::PowerSystem() {
}

/**********  Public Functions **********/
void PowerSystem::setPowerPin(int pin) {
  powerPin = pin;
  pinMode(powerPin, OUTPUT);
  on();
}

void PowerSystem::setTime(int time) {
  powerOffTime = time;
}

void PowerSystem::on() {
  digitalWrite(powerPin, HIGH);
}

void PowerSystem::off() {
  digitalWrite(powerPin, LOW);
}


void PowerSystem::offTick() {
 return;
}
