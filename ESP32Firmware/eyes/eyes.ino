#include "eye_manager.h"

EyeManager eyes;

void printHelp() {
    Serial.println("Commands:");
    Serial.println("  idle");
    Serial.println("  happy");
    Serial.println("  sad");
    Serial.println("  angry");
    Serial.println("  curious");
    Serial.println("  sleepy");
    Serial.println("  wink");
    Serial.println("  surprised");
    Serial.println("  confused");
    Serial.println("  love");
    Serial.println("  blink");
}

void handleCommand(String command) {
    command.trim();
    command.toLowerCase();

    if (command == "idle") {
        eyes.setExpression(EyeManager::IDLE);
    } else if (command == "happy") {
        eyes.setExpression(EyeManager::HAPPY);
    } else if (command == "sad") {
        eyes.setExpression(EyeManager::SAD);
    } else if (command == "angry") {
        eyes.setExpression(EyeManager::ANGRY);
    } else if (command == "curious") {
        eyes.setExpression(EyeManager::CURIOUS);
    } else if (command == "sleepy") {
        eyes.setExpression(EyeManager::SLEEPY);
    } else if (command == "wink") {
        eyes.setExpression(EyeManager::WINK);
    } else if (command == "surprised") {
        eyes.setExpression(EyeManager::SURPRISED);
    } else if (command == "confused") {
        eyes.setExpression(EyeManager::CONFUSED);
    } else if (command == "love") {
        eyes.setExpression(EyeManager::LOVE);
    } else if (command == "blink") {
        eyes.setExpression(EyeManager::BLINK);
    } else if (command == "help") {
        printHelp();
        return;
    } else {
        Serial.println("Unknown command. Type 'help'.");
        return;
    }

    Serial.print("Expression: ");
    Serial.println(command);
}

void setup() {
    Serial.begin(115200);
    delay(100);

    if (!eyes.begin(0x3C, 0x3D)) {
        Serial.println("EyeManager initialization failed.");
        while (true) {
            delay(1000);
        }
    }

    Serial.println("EyeManager ready. Starting in IDLE.");
    printHelp();
}

void loop() {
    eyes.update();

    if (Serial.available()) {
        handleCommand(Serial.readStringUntil('\n'));
    }
}
