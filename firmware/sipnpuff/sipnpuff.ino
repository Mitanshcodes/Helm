// OWNER: P2
// Sip-and-puff sensor firmware for a classic 5 V Arduino (Uno R3, Nano, Mega). docs/SPEC.md section 10.
//
// Streams one line every 10 ms (100 Hz) over USB serial at 115200 baud:
//
//     P,<millis>,<millivolts>
//
// <millivolts> is the SENSOR's output voltage (about 2500 at rest, up when you puff, down when you
// sip). The UNO Q sketch (firmware/sipnpuff_unoq) reports the same quantity, so the laptop side
// works with either board unchanged. This sketch only streams numbers: every threshold lives on the
// laptop in helm/sipnpuff.py, so it never needs re-uploading to retune.
//
// Wiring (three wires, no breadboard, no resistors: this board's pins are 5 V):
//     sensor VCC (+)  ->  5V
//     sensor GND (-)  ->  GND
//     sensor OUT (A)  ->  A0
// Tube on one sensor nozzle, the other nozzle open to the air.

const int SENSOR_PIN = A0;
const unsigned long PERIOD_MS = 10;      // 100 lines per second
const int SAMPLES = 8;                   // readings averaged per line, to smooth noise
const long ADC_REF_MV = 5000;            // analog reference: the 5 V supply, which also powers the
                                         // sensor, so supply wobble cancels out (the sensor is ratiometric)
const long ADC_MAX = 1023;               // 10-bit converter

unsigned long next_ms = 0;

void setup() {
  Serial.begin(115200);
  analogRead(SENSOR_PIN);                // first reading after power-up can be off; throw it away
  next_ms = millis();
}

void loop() {
  unsigned long now = millis();
  if ((long)(now - next_ms) < 0) {
    return;                              // not time yet
  }
  next_ms += PERIOD_MS;
  if ((long)(now - next_ms) > (long)PERIOD_MS) {
    next_ms = now + PERIOD_MS;           // fell behind (e.g. serial was busy): don't try to catch up
  }

  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogRead(SENSOR_PIN);
  }
  long mv = (sum * ADC_REF_MV) / (ADC_MAX * SAMPLES);

  Serial.print("P,");
  Serial.print(now);
  Serial.print(',');
  Serial.println(mv);
}
