#include "eye_manager.h"

EyeManager eyes;

namespace {
constexpr size_t INPUT_BUFFER_SIZE = 24;
char inputBuffer[INPUT_BUFFER_SIZE];
size_t inputLength = 0;
}

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
      if (inputLength > 0) {
        inputBuffer[inputLength] = '\0';
        eyes.handleCommand(inputBuffer);
        inputLength = 0;
        inputBuffer[0] = '\0';
      }
      continue;
    }

    if (inputLength < INPUT_BUFFER_SIZE - 1) {
      inputBuffer[inputLength++] = c;
    } else {
      // Reject an overlong command rather than growing memory or overflowing
      // the fixed buffer. The next line ending resets the command state.
      inputLength = 0;
      inputBuffer[0] = '\0';
    }
  }

  eyes.update();
}