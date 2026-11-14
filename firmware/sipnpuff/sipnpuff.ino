// OWNER: P2
// ESP32 sip-and-puff sensor: streams raw pressure readings (docs/SPEC.md section 10). Bootstrap stub.
//
// Wiring: sensor OUT -> 10 kOhm -> GPIO34 -> 20 kOhm -> GND. Never connect the 5 V output straight to a GPIO.
// Every threshold lives on the laptop (helm/sipnpuff.py); the firmware only streams.

const int SENSOR_PIN = 34;   // ADC1 pin

void setup() {
  Serial.begin(115200);
  // TODO(P2): analogSetPinAttenuation(SENSOR_PIN, ADC_11db);
}

void loop() {
  // TODO(P2): every 10 ms, average 8 readings of analogReadMilliVolts(SENSOR_PIN)
  // and print "P,<millis>,<millivolts>".
  delay(10);
}
