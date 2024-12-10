


// Game Update time
#define GAME_SPEED 50
// Initialise 'sprites'
#define SPRITE_HEIGHT   16
#define SPRITE_WIDTH    16
// pin the flap button is attached to
#define FLAP_BUTTON  triggerBtn


// Game variables
int game_state = 1;                         // 0 = game over screen, 1 = in game
int score = 0;                              // current game score
int high_score = 0;                         // highest score since the nano was reset
int bird_x = (int)OLED.getWidth() / 4;      // birds x position (along) - initialised to 1/4 the way along the screen
int bird_y;                                 // birds y position (down)
int momentum = 0;                           // how much force is pulling the bird down
int wall_gap = 30;                          // size of the wall wall_gap in pixels
int wall_width = 10;                        // width of the wall in pixels


// Two frames of animation
uint8_t wing_down_bmp[] =
{ 0b11000000,
  0b11100000,
  0b01110000,
  0b11111000,
  0b11111000,
  0b11111000,
  0b11111100,
  0b11111100,
  0b11101100,
  0b11101100,
  0b10111000,
  0b10111000,
  0b10110000,
  0b10100000,
  0b10100000,
  0b01000000,
  0b00001111,
  0b00011111,
  0b00111000,
  0b00111011,
  0b00110111,
  0b01110111,
  0b01110111,
  0b01111000,
  0b00111111,
  0b00111111,
  0b00011111,
  0b00001111,
  0b00000111,
  0b00000000,
  0b00000000,
  0b00000000,
};


uint8_t wing_up_bmp[] =
{ 0b11000000,
  0b11100000,
  0b01110000,
  0b10111000,
  0b11011000,
  0b11011000,
  0b11011100,
  0b10111100,
  0b01101100,
  0b11101100,
  0b10111000,
  0b10111000,
  0b10110000,
  0b10100000,
  0b10100000,
  0b01000000,
  0b00001111,
  0b00011111,
  0b00111110,
  0b00111111,
  0b00111111,
  0b01111111,
  0b01111111,
  0b01111111,
  0b00111110,
  0b00111111,
  0b00011111,
  0b00001111,
  0b00000111,
  0b00000000,
  0b00000000,
  0b00000000,
};


/*

static const unsigned char PROGMEM wing_down_bmp[] =
{ B00000000, B00000000,
  B00000000, B00000000,
  B00000011, B11000000,
  B00011111, B11110000,
  B00111111, B00111000,
  B01111111, B11111110,
  B11111111, B11000001,
  B11011111, B01111110,
  B11011111, B01111000,
  B11011111, B01111000,
  B11001110, B01111000,
  B11110001, B11110000,
  B01111111, B11100000,
  B00111111, B11000000,
  B00000111, B00000000,
  B00000000, B00000000,
};

static const unsigned char PROGMEM wing_up_bmp[] =
{ B00000000, B00000000,
  B00000000, B00000000,
  B00000011, B11000000,
  B00011111, B11110000,
  B00111111, B00111000,
  B01110001, B11111110,
  B11101110, B11000001,
  B11011111, B01111110,
  B11011111, B01111000,
  B11111111, B11111000,
  B11111111, B11111000,
  B11111111, B11110000,
  B01111111, B11100000,
  B00111111, B11000000,
  B00000111, B00000000,
  B00000000, B00000000,
};
*/

void oled_print_center_no_erase(String text = "", bool color = false) {
  int x = (OLED.getWidth() - OLED.getStringWidth(text)) / 2;
  int y = (OLED.getStringHeight(text) + 5);
  OLED.text(x, y, text, !color);
  OLED.display();
}

void flapp_start() {
  int wall_x_0 = OLED.getWidth() ;
  int wall_y_0 = OLED.getHeight() / 2 - wall_gap / 2;
  int wall_x_1 = OLED.getWidth() + OLED.getWidth() / 2;
  int wall_y_1 = OLED.getHeight() / 2 - wall_gap / 1;

  // Initialise the random number generator
  randomSeed(analogRead(0));

  game_state = 0;
  int score = 0;
  while (game_state == 0) {
    OLED.erase();

    // If the flap button is currently pressed, reduce the downward force on the bird a bit.
    // Once this foce goes negative the bird goes up, otherwise it falls towards the ground
    // gaining speed
    if (digitalRead(FLAP_BUTTON)) {
      momentum = -4;
    }

    // increase the downward force on the bird
    momentum += 1;

    // add the downward force to the bird position to determine it's new position
    bird_y += momentum;

    // make sure the bird doesn't fly off the top of the screen
    if (bird_y < 0 ) {
      bird_y = 0;
    }


    // make sure the bird doesn't fall off the bottom of the screen
    // give it a slight positive lift so it 'waddles' along the ground.
    if (bird_y > OLED.getHeight() - SPRITE_HEIGHT) {
      bird_y = OLED.getHeight() - SPRITE_HEIGHT;
      momentum = -2;
    }

    // display the bird
    // if the momentum on the bird is negative the bird is going up!
    if (momentum < 0) {

      // display the bird using a randomly picked flap animation frame
      if (random(2) == 0) {
        
        OLED.bitmap(bird_x, bird_y, wing_down_bmp, 16, 16);
      }
      else {
        OLED.bitmap(bird_x, bird_y, wing_up_bmp, 16, 16);
      }

    }
    else {

      // bird is currently falling, use wing up frame
      OLED.bitmap(bird_x, bird_y, wing_up_bmp, 16, 16);

    }

    OLED.rectangleFill(wall_x_0, 0, wall_width, wall_y_0, true);
    OLED.rectangleFill(wall_x_1, 0, wall_width, wall_y_1, true);


    Serial.println(wall_x_0);
    Serial.println(wall_y_0);
    Serial.println(wall_x_1);
    Serial.println(wall_y_1);
    Serial.println("#");

    OLED.rectangleFill(wall_x_0, wall_y_0 + wall_gap, wall_width, OLED.getHeight() - wall_y_0 + wall_gap, true);
    OLED.rectangleFill(wall_x_1, wall_y_1 + wall_gap, wall_width, OLED.getHeight() - wall_y_1 + wall_gap, true);

    if (wall_x_0 < 0) {
      wall_y_0 = random(0, OLED.getHeight() - wall_gap);
      wall_x_0 = OLED.getWidth();
    }

    if (wall_x_1 < 0) {
      wall_y_1 = random(0, OLED.getHeight() - wall_gap);
      wall_x_1 = OLED.getWidth();
    }

    wall_x_0 -= 4;
    wall_x_1 -= 4;


    // display the current score
    oled_print_center_no_erase((String)score);

    OLED.display();
    delay(GAME_SPEED);
  }
}

/*

void flapp_start() {

 

    // now we draw the walls and see if the player has hit anything
    for (int i = 0 ; i < 2; i++) {
      Serial.println(i);

      
      Serial.println("a");
      
      Serial.println("b");
      // if the wall has hit the edge of the screen
      // reset it back to the other side with a new gap position
      
      Serial.println("c");
      // if the bird has passed the wall, update the score
      if (wall_x[i] == bird_x) {
        score++;

        // highscore is whichever is bigger, the current high score or the current score
        high_score = max(score, high_score);
      }
      Serial.println("d");
      // if the bird is level with the wall and not level with the gap - game over!
      if (
        (bird_x + SPRITE_WIDTH > wall_x[i] && bird_x < wall_x[i] + wall_width) // level with wall
        &&
        (bird_y < wall_y[i] || bird_y + SPRITE_HEIGHT > wall_y[i] + wall_gap) // not level with the gap
      ) {
        
        // display the crash and pause 1/2 a second
        OLED.display();
        delay(500);

        // switch to game over state
        game_state = 1; 

      }
      
    }

    Serial.println("4");

    // display the current score
    oled_print_center_no_erase((String)score);

    // now display everything to the user and wait a bit to keep things playable
    
    

    Serial.println("5");
  }
}


*/

























/*

void flapp_start() {

  wall_x[0] = OLED.getWidth() ;
  wall_y[0] = OLED.getHeight() / 2 - wall_gap / 2;
  wall_x[1] = OLED.getWidth() + OLED.getWidth() / 2;
  wall_y[1] = OLED.getHeight() / 2 - wall_gap / 1;


  Serial.println("0");
  // Initialise the random number generator
  randomSeed(analogRead(0));
  
  game_state = 0;
  Serial.println("1");
  while (game_state == 0) {
    // in game
    OLED.erase();

    // If the flap button is currently pressed, reduce the downward force on the bird a bit.
    // Once this foce goes negative the bird goes up, otherwise it falls towards the ground
    // gaining speed
    if (digitalRead(FLAP_BUTTON)) {
      momentum = -4;
    }

    // increase the downward force on the bird
    momentum += 1;

    // add the downward force to the bird position to determine it's new position
    bird_y += momentum;

    // make sure the bird doesn't fly off the top of the screen
    if (bird_y < 0 ) {
      bird_y = 0;
    }

    // make sure the bird doesn't fall off the bottom of the screen
    // give it a slight positive lift so it 'waddles' along the ground.
    if (bird_y > OLED.getHeight() - SPRITE_HEIGHT) {
      bird_y = OLED.getHeight() - SPRITE_HEIGHT;
      momentum = -2;
    }

    Serial.println("2");

    // display the bird
    // if the momentum on the bird is negative the bird is going up!
    if (momentum < 0) {

      // display the bird using a randomly picked flap animation frame
      if (random(2) == 0) {
        
        OLED.bitmap(bird_x, bird_y, wing_down_bmp, 16, 16);
      }
      else {
        OLED.bitmap(bird_x, bird_y, wing_up_bmp, 16, 16);
      }

    }
    else {

      // bird is currently falling, use wing up frame
      OLED.bitmap(bird_x, bird_y, wing_up_bmp, 16, 16);

    }

    Serial.println("3");

    // now we draw the walls and see if the player has hit anything
    for (int i = 0 ; i < 2; i++) {
      Serial.println(i);

      // draw the top half of the wall
      OLED.rectangleFill(wall_x[i], 0, wall_width, wall_y[i], true);
      Serial.println("a");
      // draw the bottom half of the wall
      OLED.rectangleFill(wall_x[i], wall_y[i] + wall_gap, wall_width, OLED.getHeight() - wall_y[i] + wall_gap, true);
      Serial.println("b");
      // if the wall has hit the edge of the screen
      // reset it back to the other side with a new gap position
      if (wall_x[i] < 0) {
        wall_y[i] = random(0, OLED.getHeight() - wall_gap);
        wall_x[i] = OLED.getWidth();
      }
      Serial.println("c");
      // if the bird has passed the wall, update the score
      if (wall_x[i] == bird_x) {
        score++;

        // highscore is whichever is bigger, the current high score or the current score
        high_score = max(score, high_score);
      }
      Serial.println("d");
      // if the bird is level with the wall and not level with the gap - game over!
      if (
        (bird_x + SPRITE_WIDTH > wall_x[i] && bird_x < wall_x[i] + wall_width) // level with wall
        &&
        (bird_y < wall_y[i] || bird_y + SPRITE_HEIGHT > wall_y[i] + wall_gap) // not level with the gap
      ) {
        
        // display the crash and pause 1/2 a second
        OLED.display();
        delay(500);

        // switch to game over state
        game_state = 1; 

      }
      
      // move the wall left 4 pixels
      wall_x[i] -= 4;
    }

    Serial.println("4");

    // display the current score
    oled_print_center_no_erase((String)score);

    // now display everything to the user and wait a bit to keep things playable
    OLED.display();
    delay(GAME_SPEED);

    Serial.println("5");
  }
}


*/


/*

void test() {

  if (game_state == 0) {
    // in game
    display.clearDisplay();

    // If the flap button is currently pressed, reduce the downward force on the bird a bit.
    // Once this foce goes negative the bird goes up, otherwise it falls towards the ground
    // gaining speed
    if (digitalRead(FLAP_BUTTON) == LOW) {
      momentum = -4;
    }

    // increase the downward force on the bird
    momentum += 1;

    // add the downward force to the bird position to determine it's new position
    bird_y += momentum;

    // make sure the bird doesn't fly off the top of the screen
    if (bird_y < 0 ) {
      bird_y = 0;
    }

    // make sure the bird doesn't fall off the bottom of the screen
    // give it a slight positive lift so it 'waddles' along the ground.
    if (bird_y > display.height() - SPRITE_HEIGHT) {
      bird_y = display.height() - SPRITE_HEIGHT;
      momentum = -2;
    }

    // display the bird
    // if the momentum on the bird is negative the bird is going up!
    if (momentum < 0) {

      // display the bird using a randomly picked flap animation frame
      if (random(2) == 0) {
        display.drawBitmap(bird_x, bird_y, wing_down_bmp, 16, 16, WHITE);
      }
      else {
        display.drawBitmap(bird_x, bird_y, wing_up_bmp, 16, 16, WHITE);
      }

    }
    else {

      // bird is currently falling, use wing up frame
      display.drawBitmap(bird_x, bird_y, wing_up_bmp, 16, 16, WHITE);

    }

    // now we draw the walls and see if the player has hit anything
    for (int i = 0 ; i < 2; i++) {

      // draw the top half of the wall
      display.fillRect(wall_x[i], 0, wall_width, wall_y[i], WHITE);

      // draw the bottom half of the wall
      display.fillRect(wall_x[i], wall_y[i] + wall_gap, wall_width, display.height() - wall_y[i] + wall_gap, WHITE);

      // if the wall has hit the edge of the screen
      // reset it back to the other side with a new gap position
      if (wall_x[i] < 0) {
        wall_y[i] = random(0, display.height() - wall_gap);
        wall_x[i] = display.width();
      }

      // if the bird has passed the wall, update the score
      if (wall_x[i] == bird_x) {
        score++;

        // highscore is whichever is bigger, the current high score or the current score
        high_score = max(score, high_score);
      }

      // if the bird is level with the wall and not level with the gap - game over!
      if (
        (bird_x + SPRITE_WIDTH > wall_x[i] && bird_x < wall_x[i] + wall_width) // level with wall
        &&
        (bird_y < wall_y[i] || bird_y + SPRITE_HEIGHT > wall_y[i] + wall_gap) // not level with the gap
      ) {
        
        // display the crash and pause 1/2 a second
        display.display();
        delay(500);

        // switch to game over state
        game_state = 1; 

      }

      // move the wall left 4 pixels
      wall_x[i] -= 4;
    }

    // display the current score
    boldTextAtCenter(0, (String)score);

    // now display everything to the user and wait a bit to keep things playable
    display.display();
    delay(GAME_SPEED);

  }
  else {

    // game over screen

    screenWipe(10);

    outlineTextAtCenter(1, "NANO BIRD");
    
    textAtCenter(display.height() / 2 - 8, "GAME OVER");
    textAtCenter(display.height() / 2, String(score));
    
    boldTextAtCenter(display.height() - 16, "HIGH SCORE");
    boldTextAtCenter(display.height()  - 8, String(high_score));

    display.display();

    // wait while the user stops pressing the button
    while (digitalRead(FLAP_BUTTON) == LOW);

    // setup a new game
    bird_y = display.height() / 2;
    momentum = -4;
    wall_x[0] = display.width() ;
    wall_y[0] = display.height() / 2 - wall_gap / 2;
    wall_x[1] = display.width() + display.width() / 2;
    wall_y[1] = display.height() / 2 - wall_gap / 1;
    score = 0;

    // wait until the user presses the button
    while (digitalRead(FLAP_BUTTON) == HIGH);

    // start a new game
    screenWipe(10);
    game_state = 0;
    
  }

}


// clear the screen using a wipe down animation

void screenWipe(int speed) {

  // progressivly fill screen with white
  for (int i = 0; i < display.height(); i += speed) {
    display.fillRect(0, i, display.width(), speed, WHITE);
    display.display();
  }

  // progressively fill the screen with black
  for (int i = 0; i < display.height(); i += speed) {
    display.fillRect(0, i, display.width(), speed, BLACK);
    display.display();
  }

}


// displays txt at x,y coordinates

void textAt(int x, int y, String txt) {
  display.setCursor(x, y);
  display.print(txt);
}


// displays text centered on the line

void textAtCenter(int y, String txt) {
  textAt(display.width() / 2 - txt.length() * 3, y, txt);
}


// displays outlined text centered on the line

void outlineTextAtCenter(int y, String txt) {
  int x = display.width() / 2 - txt.length() * 3;

  display.setTextColor(WHITE);
  textAt(x - 1, y, txt);
  textAt(x + 1, y, txt);
  textAt(x, y - 1, txt);
  textAt(x, y + 1, txt);

  display.setTextColor(BLACK);
  textAt(x, y, txt);
  display.setTextColor(WHITE);

}

// displays bold text centered on the line

void boldTextAtCenter(int y, String txt) {
  int x = display.width() / 2 - txt.length() * 3;

  textAt(x, y, txt);
  textAt(x + 1, y, txt);

}

*/

