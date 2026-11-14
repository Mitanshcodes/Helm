// OWNER: P2
// Just for fun: "6-7" on the Arduino UNO Q's 8x13 LED matrix, with the 6 and the 7 bobbing up
// and down in turn like the hand gesture.
//
// Uploading this REPLACES the breath-sensor code on the board. Re-upload
// firmware/sipnpuff_unoq/sipnpuff_unoq.ino afterwards to get the sensor back.

#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

const int W = 13;                  // columns
const int H = 8;                   // rows
uint8_t frame[W * H];              // brightness per LED, 0 (off) to 7 (full)

// Each digit is 4 columns x 7 rows. 1 = LED on.
const uint8_t SIX[7][4] = {
  {0, 1, 1, 1},
  {1, 0, 0, 0},
  {1, 0, 0, 0},
  {1, 1, 1, 0},
  {1, 0, 0, 1},
  {1, 0, 0, 1},
  {0, 1, 1, 0},
};
const uint8_t SEVEN[7][4] = {
  {1, 1, 1, 1},
  {0, 0, 0, 1},
  {0, 0, 1, 0},
  {0, 0, 1, 0},
  {0, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 0, 0},
};

const int BOB_MS = 250;            // how long each up/down step lasts: smaller = faster bobbing

void drawDigit(const uint8_t digit[7][4], int left_col, int top_row) {
  for (int r = 0; r < 7; r++) {
    for (int c = 0; c < 4; c++) {
      if (digit[r][c]) {
        frame[(top_row + r) * W + left_col + c] = 7;
      }
    }
  }
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);      // 3 bits = 8 brightness levels
}

void loop() {
  static bool six_up = true;

  for (int i = 0; i < W * H; i++) {
    frame[i] = 0;
  }

  // Layout across the 13 columns: 6 (cols 0-3), gap, dash (cols 5-7), gap, 7 (cols 9-12).
  drawDigit(SIX, 0, six_up ? 0 : 1);
  drawDigit(SEVEN, 9, six_up ? 1 : 0);
  for (int c = 5; c <= 7; c++) {
    frame[4 * W + c] = 3;          // the dash, a bit dimmer than the digits
  }

  matrix.draw(frame);
  six_up = !six_up;
  delay(BOB_MS);
}
