// OWNER: P2
// Sip-and-puff sensor firmware for the Arduino UNO Q. docs/SPEC.md section 10.
//
// Streams one line every 10 ms (100 Hz) to the laptop:
//
//     P,<millis>,<millivolts>
//
// <millivolts> is the SENSOR's output voltage (about 2500 at rest, up when you puff, down when you
// sip), worked back from the divided voltage at A2. The classic-Arduino sketch (firmware/sipnpuff)
// reports the same quantity, so the laptop side works with either board unchanged. This sketch only
// streams numbers: every threshold lives on the laptop in helm/sipnpuff.py.
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

const int SENSOR_PIN = A2;
const unsigned long PERIOD_MS = 10;      // 100 lines per second
const int SAMPLES = 8;                   // readings averaged per line, to smooth noise
const long ADC_REF_MV = 3300;            // the UNO Q converter measures 0 to 3.3 V
const long ADC_MAX = 16383;              // 14-bit converter
const long DIVIDER = 2;                  // R1 = R2 = 10k halves the sensor voltage; undo it here

unsigned long next_ms = 0;

void setup() {
  Monitor.begin();
  analogReadResolution(14);
  analogRead(SENSOR_PIN);                // first reading can be off; throw it away
  next_ms = millis();
}

void loop() {
  unsigned long now = millis();
  if ((long)(now - next_ms) < 0) {
    return;                              // not time yet
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
