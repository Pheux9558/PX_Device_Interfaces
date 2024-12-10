//#include "LiquidCrystal_Software_I2C.h"
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include "settings.h"




// !!! FIRMWARE need to be set !!!  (GPIO_lib_uno/GPIO_lib_mega)
#define FIRMWARE "GPIO_lib_mega"
#include <Servo.h>
#define MAX_BUF (64)
#define BAUD (115200)
//#define analog_start_pin 14

char buffer[MAX_BUF]; // where we store the message until we get a ';'
int sofar; // how much is in the buffer
int msg_from_port=0;
bool use_update = true; // use pin update function
int update_val = 0;  // carry for update
unsigned long previousMillis = 0;
const long interval = 10;
#define analog_tolerance 10
Servo servos[8];
//LiquidCrystal_I2C lcd(0x27, 20, 4, 3, 4);
LiquidCrystal_I2C lcd(0x27, 20, 4);

void setup() {
  // put your setup code here, to run once:
  Serial.begin(BAUD);
  Serial1.begin(BAUD);
  Serial2.begin(BAUD);
  //lcd.init();
  lcd.begin();
  //lcd.backlight();
  lcd.print("GPIO_Lib");
  lcd.setCursor(0,1);
  lcd.print("init remote");
  sofar=0;
  for(int i = 0; i < io_pins; i++) {
    input_array[i][1] = 0;
  }
  Serial.println(">");
  Serial1.println(">");
  Serial2.println(">");
}


void setup_data(int mode) {
  switch(mode) {
    case 0: use_update != use_update; break;
    default: break;
  }
}

void set_input_digital(int pin_num){
  if (pin_num > 0) {
    pinMode(pin_num, INPUT);
    input_array[pin_num][0] = 1;
  }
}

void set_input_analog(int pin_num){
  if (pin_num > 0) {
    pinMode(pin_num, INPUT_PULLUP);
    input_array[pin_num][0] = 2;
  }
}

void set_output(int pin_num){
  if (pin_num > 0) {
    pinMode(pin_num, OUTPUT);
  }
}

void set_input_pullup(int pin_num){
  if (pin_num > 0) {
    pinMode(pin_num, INPUT_PULLUP);
    input_array[pin_num][0] = 1;
  }
}

void set_servo(int pin_num, int servo_index){
  if (pin_num > 0) {
    servos[servo_index].attach(pin_num);
  }
}

void digital_read(int pin_num){
  if (pin_num > 0) {
    String send_val = "";
    if (digitalRead(pin_num) == HIGH)
      send_val = "1";
    else
      send_val = "0";
    switch(msg_from_port) {
      case 0: Serial.println(send_val); break;
      case 1: Serial1.println(send_val); break;
      case 2: Serial2.println(send_val); break;
      default: break;
    } 
  }
}


void digital_write(int pin_num, int set_val){
  if (pin_num > 0) {
    if (set_val==0)
      digitalWrite(pin_num, LOW);
    else
      digitalWrite(pin_num, HIGH);
  }
}


void analog_read(int pin_num){
  if (pin_num > 0) {
    switch(msg_from_port) {
      case 0: Serial.println(analogRead(pin_num)); break;
      case 1: Serial1.println(analogRead(pin_num)); break;
      case 2: Serial2.println(analogRead(pin_num)); break;
      default: break;
    } 
  }
}

void analog_write(int pin_num, int set_val){
  if (pin_num > 0) {
      analogWrite(pin_num, set_val);
  }
}

void servo_write(int servo_index, int set_val){
  servos[servo_index].write(set_val);
}


void lcd_system(){
  int cmd=parsenumber('A',-1); // look for commands that start with 'A'
  String str1;
  String serial_lcd_line;
  switch(cmd) {
    case 1: 
        switch(msg_from_port) {
          case 0: 
              Serial.println(">");
              while(Serial.available() == 0){}// until something is available
              while(Serial.available() > 0){
                char lcd_text=Serial.read(); 
                if (lcd_text!='\n'){lcd.print(lcd_text);}else{break;}}  break;
          case 1: 
              Serial1.println(">");
              while(Serial1.available() == 0){}// until something is available
              while(Serial1.available() > 0){
                char lcd_text=Serial1.read(); 
                if (lcd_text!='\n'){lcd.print(lcd_text);}else{break;}}  break;
          case 2: 
              Serial2.println(">");
              while(Serial2.available() == 0){}// until something is available
              while(Serial2.available() > 0){
                char lcd_text=Serial2.read(); 
                if (lcd_text!='\n' and lcd_text!='\r'){lcd.print(lcd_text);}else{break;}}  break;
          default: break;
        } 
          break;
    case 2:
          lcd.setCursor(int(parsenumber('X',-1)),int(parsenumber('Y',-1)));
          break;
    case 3:
          lcd.clear();
          break;
    default: break;
  }
}


void firmware_callback() {
  switch(msg_from_port) {
    case 0: Serial.println(FIRMWARE); break;
    case 1: Serial1.println(FIRMWARE); break;
    case 2: Serial2.println(FIRMWARE); break;
    default: break;
  } 
}


float parsenumber(char code,float val) {
  char *ptr=buffer;  // start at the beginning of buffer
  while((long)ptr > 1 && (*ptr) && (long)ptr < (long)buffer+sofar) {  // walk to the end
    if(*ptr==code) {  // if you find code on your walk,
      return atof(ptr+1);  // convert the digits that follow into a float and return it
    }
    ptr=strchr(ptr,' ')+1;  // take a step from here to the letter after the next space
  }
  
  return val;  // end reached, nothing found, return default val.
}



void processCommand(){
  int cmd=parsenumber('M',-1); // look for commands that start with 'M'
  switch(cmd) {
    case 0: setup_data(parsenumber('N',-1));
    case 1: set_input_digital(parsenumber('N',-1)); break;
    case 2: set_output(parsenumber('N',-1)); break;
    case 3: set_input_pullup(parsenumber('N',-1)); break;
    case 4: set_input_analog(parsenumber('N',-1)); break;
    case 5: set_servo(parsenumber('N',-1),parsenumber('A',-1)); break;
    case 100: firmware_callback(); break;
    case 999: Serial.println("#RESET#"); Serial1.println("#RESET#"); Serial2.println("#RESET#"); break;   // RESET WiFi
    default: break;
  }

  
  cmd=parsenumber('P',-1); // look for commands that start with 'P'
  switch(cmd) {
    case 1: digital_read(parsenumber('N',-1)); break;
    case 2: digital_write(parsenumber('N',-1), parsenumber('V',-1)); break;
    case 3: analog_read(parsenumber('N',-1)); break;
    case 4: analog_write(parsenumber('N',-1), parsenumber('V',-1)); break;
    case 5: servo_write(parsenumber('N',-1), parsenumber('V',-1)); break;
    case 6: lcd_system(); break;
    default: break;
  }
  
}






void loop() {
  if (use_update){   //send changed val
    unsigned long currentMillis = millis();
    if(currentMillis - previousMillis >= interval){
      previousMillis = currentMillis;
      for(int i = 0; i < io_pins; i++) {
        // Serial.print(i);Serial.print(":");Serial.print(input_array[i][0])Serial.print(",");Serial.println(input_array[i][1]);
        switch(input_array[i][0]) {
          case 0: continue;  // Skip this pin
          case 1: 
            //Serial.println(digitalRead(i)); 
            if(digitalRead(i) == HIGH) {update_val = 0;}else{update_val = 1;}
            if(update_val != input_array[i][1]) {  // Digital read, if val dif => update array and send to serial
              input_array[i][1] = update_val;
              switch(msg_from_port) {
                case 0: Serial.println("d:" + String(i) + ":" + String(update_val));continue;
                case 1: Serial1.println("d:" + String(i) + ":" + String(update_val));continue;
                case 2: Serial2.println("d:" + String(i) + ":" + String(update_val));continue;
                default: continue;
              } 
            }
            continue;
          case 2: 
            update_val = analogRead(i);
            if ((update_val > input_array[i][1] + analog_tolerance) or
              (update_val < input_array[i][1] - analog_tolerance)) {  // Analog read, if val dif => update array and send to serial
              //if(update_val != input_array[i][1])
              input_array[i][1] = update_val;
              switch(msg_from_port) {
                case 0: Serial.println("a:" + String(i) + ":" + String(update_val));continue;
                case 1: Serial1.println("a:" + String(i) + ":" + String(update_val));continue;
                case 2: Serial2.println("a:" + String(i) + ":" + String(update_val));continue;
                default: continue;
              } 
            }
            continue;
          default: 
            Serial.print("ERROR: update array[i=");
            Serial.print(i);
            Serial.print(",");
            Serial.print(input_array[i][0]);
            Serial.println(")");
            continue;
        }
      }
    }
  }

  while(Serial.available() > 0) {  // if something is available
    char c=Serial.read();  // get it
    //Serial.print(c);  // repeat it back so I know you got the message
    if(sofar<MAX_BUF-1) buffer[sofar++]=c;  // store it
    if((c=='\n') || (c == '\r')|| (c == ';')) {
      // entire message received
      buffer[sofar]=0;  // end the buffer so string functions work right
      //Serial.print(F("\r\n"));  // echo a return character for humans
      msg_from_port=0;
      processCommand();  // do something with the command
      sofar=0;
      Serial.println(">");
    }
  }

  while(Serial1.available() > 0) {  // if something is available
    char c=Serial1.read();  // get it
    //Serial.print(c);  // repeat it back so I know you got the message
    if(sofar<MAX_BUF-1) buffer[sofar++]=c;  // store it
    if((c=='\n') || (c == '\r')|| (c == ';')) {
      // entire message received
      buffer[sofar]=0;  // end the buffer so string functions work right
      //Serial.print(F("\r\n"));  // echo a return character for humans
      msg_from_port=1;
      processCommand();  // do something with the command
      sofar=0;
      Serial1.println(">");
    }
  }

  while(Serial2.available() > 0) {  // if something is available
    char c=Serial2.read();  // get it
    Serial.print(c);  // repeat it back so I know you got the message
    if(sofar<MAX_BUF-1) buffer[sofar++]=c;  // store it
    if((c=='\n') || (c == ';')) {
      // entire message received
      buffer[sofar]=0;  // end the buffer so string functions work right
      //Serial.print(F("\r\n"));  // echo a return character for humans
      msg_from_port=2;
      processCommand();  // do something with the command
      sofar=0;
      Serial2.println(">");
    }
  }

  
}
