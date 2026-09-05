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

bool handleCommand(String command) {
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
        return true;
    } else {
        Serial.println("Unknown command. Type 'help'.");
        return false;
    }

    Serial.print("Expression: ");
    Serial.println(command);
    return true;
}

void setup() {
    Serial.begin(115200);
    delay(100);

    // Both OLEDs share SDA=21 and SCL=22.
    // The displays must have different I2C addresses.
    if (!eyes.begin(0x3C, 0x3D)) {
        Serial.println("EyeManager initialization failed.");
        while (true) {
            delay(1000);
        }
    }

    // Robot starts in stable idle. No automatic expression cycling.
    Serial.println("EyeManager ready. Starting in IDLE.");
    printHelp();
}

void loop() {
    eyes.update();

    if (Serial.available()) {
        const String command = Serial.readStringUntil('\n');
        handleCommand(command);
    }
}
