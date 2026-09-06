#include "eye_manager.h"

EyeManager eyes;
String inputBuffer = "";

void setup() {
  Serial.begin(115200);

  eyes.begin();
  eyes.setExpression(EXPR_IDLE);

  Serial.println();
  Serial.println(F("THASHU ESP32 DUAL-OLED SYNCHRONIZED EYE SYSTEM"));
  eyes.printHelp();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        eyes.handleCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }

  eyes.update();
}