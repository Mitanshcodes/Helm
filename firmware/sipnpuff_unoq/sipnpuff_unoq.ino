// OWNER: P2
// Sip-and-puff sensor firmware for the Arduino UNO Q. docs/SPEC.md section 10.
//
// Streams one line per reading to the laptop (about 68 per second on the UNO Q):
//
//     P,<millis>,<millivolts>
//
// <millivolts> is the SENSOR's output voltage (about 2500 at rest, up when you puff, down when you
// sip), worked back from the divided voltage at A2. The classic-Arduino sketch (firmware/sipnpuff)
// reports the same quantity, so the laptop side works with either board unchanged. This sketch only
// streams numbers: every threshold lives on the laptop in helm/sipnpuff.py.
//
// The LED matrix shows a bobbing "6-7" while it runs. It only redraws every BOB_MS, between
// readings, so the sensor stream keeps its rate. Set SHOW_67 to false to turn it off, and
// FLIP_HORIZONTAL / FLIP_VERTICAL to mirror it left-right or top-bottom.
//
// Wiring: see firmware/sipnpuff/wiring_breadboard.png.
//     sensor VCC  ->  5V
//     sensor GND  ->  GND
//     sensor OUT  ->  R1 (10k)  ->  A2,  and  A2 -> R2 (10k) -> GND,  and optionally A2 -> 0.1 uF -> GND
// Never connect sensor OUT straight to any UNO Q pin: its pins take 3.3 V at most.
//
// UNO Q specifics, each of which silently breaks things if ignored:
//   - Text to the laptop must go through Monitor (Arduino_RouterBridge), NOT Serial. Serial is the
//     UART on pins 0/1 and never reaches the USB-C port.
//   - Do NOT call pinMode() on SENSOR_PIN: on this board it breaks analogRead (stuck around 270).
//   - Use A2, not A0/A1. A0 and A1 are the pins that are not 5 V tolerant.

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>

// ---------------------------------------------------------------- sensor
const int SENSOR_PIN = A2;
const unsigned long PERIOD_MS = 10;      // aim for 100 lines per second (the UNO Q manages ~68)
const int SAMPLES = 8;                   // readings averaged per line, to smooth noise
const long ADC_REF_MV = 3300;            // the UNO Q converter measures 0 to 3.3 V
const long ADC_MAX = 16383;              // 14-bit converter
const long DIVIDER = 2;                  // R1 = R2 = 10k halves the sensor voltage; undo it here

unsigned long next_ms = 0;

// ---------------------------------------------------------------- LED matrix: bobbing "6-7"
const bool SHOW_67 = true;
const bool FLIP_HORIZONTAL = true;       // mirror the grid left-right (left column <-> right column)
const bool FLIP_VERTICAL = true;         // draw the grid upside-down (top row <-> bottom row)
const unsigned long BOB_MS = 250;        // how long each up/down step lasts: smaller = faster
const int W = 13;                        // columns
const int H = 8;                         // rows

Arduino_LED_Matrix matrix;
uint8_t frame[W * H];                    // brightness per LED, 0 (off) to 7 (full)
unsigned long next_bob_ms = 0;
bool six_up = true;

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

void drawDigit(const uint8_t digit[7][4], int left_col, int top_row) {
  for (int r = 0; r < 7; r++) {
    for (int c = 0; c < 4; c++) {
      if (digit[r][c]) {
        frame[(top_row + r) * W + left_col + c] = 7;
      }
    }
  }
}

void drawSixSeven() {
  for (int i = 0; i < W * H; i++) {
    frame[i] = 0;
  }
  // Layout across the 13 columns: 6 (cols 0-3), gap, dash (cols 5-7), gap, 7 (cols 9-12).
  drawDigit(SIX, 0, six_up ? 0 : 1);
  drawDigit(SEVEN, 9, six_up ? 1 : 0);
  for (int c = 5; c <= 7; c++) {
    frame[4 * W + c] = 3;                // the dash, a bit dimmer than the digits
  }
  if (FLIP_HORIZONTAL) {
    for (int r = 0; r < H; r++) {        // swap column c with its mirror column, row by row
      for (int c = 0; c < W / 2; c++) {
        uint8_t tmp = frame[r * W + c];
        frame[r * W + c] = frame[r * W + (W - 1 - c)];
        frame[r * W + (W - 1 - c)] = tmp;
      }
    }
  }
  if (FLIP_VERTICAL) {
    for (int r = 0; r < H / 2; r++) {    // swap row r with its mirror row, column by column
      for (int c = 0; c < W; c++) {
        uint8_t tmp = frame[r * W + c];
        frame[r * W + c] = frame[(H - 1 - r) * W + c];
        frame[(H - 1 - r) * W + c] = tmp;
      }
    }
  }
  matrix.draw(frame);
  six_up = !six_up;
}

// ---------------------------------------------------------------- main
void setup() {
  Monitor.begin();
  analogReadResolution(14);
  analogRead(SENSOR_PIN);                // first reading can be off; throw it away
  if (SHOW_67) {
    matrix.begin();
    matrix.setGrayscaleBits(3);          // 3 bits = 8 brightness levels
  }
  next_ms = millis();
  next_bob_ms = millis();
}

void loop() {
  unsigned long now = millis();

  // The animation is checked first and never waits, so it can't hold up a sensor reading.
  if (SHOW_67 && (long)(now - next_bob_ms) >= 0) {
    next_bob_ms = now + BOB_MS;
    drawSixSeven();
  }

  if ((long)(now - next_ms) < 0) {
    return;                              // not time for a reading yet
  }
  next_ms += PERIOD_MS;
  if ((long)(now - next_ms) > (long)PERIOD_MS) {
    next_ms = now + PERIOD_MS;           // fell behind: don't try to catch up
  }

  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogRead(SENSOR_PIN);
  }
  long pin_mv = (sum * ADC_REF_MV) / (ADC_MAX * SAMPLES);
  long mv = pin_mv * DIVIDER;

  // One Monitor call per line: each call is a separate message to the Linux side, so building the
  // whole line first keeps the rate up and stops lines from arriving in pieces.
  char line[32];
  snprintf(line, sizeof(line), "P,%lu,%ld", now, mv);
  Monitor.println(line);
}
