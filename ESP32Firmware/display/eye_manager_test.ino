#include "eye_manager.h"

EyeManager eyes;

const EyeManager::Expression EXPRESSIONS[] = {
    EyeManager::HAPPY,
    EyeManager::SAD,
    EyeManager::ANGRY,
    EyeManager::CURIOUS,
    EyeManager::SLEEPY,
    EyeManager::WINK,
    EyeManager::SURPRISED,
    EyeManager::CONFUSED,
    EyeManager::LOVE,
    EyeManager::BLINK,
};

constexpr uint8_t EXPRESSION_COUNT = sizeof(EXPRESSIONS) / sizeof(EXPRESSIONS[0]);
constexpr unsigned long EXPRESSION_HOLD_MS = 2000;

unsigned long lastExpressionChange = 0;
uint8_t expressionIndex = 0;

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

    Serial.println("EyeManager ready.");
    eyes.setExpression(EXPRESSIONS[expressionIndex]);
    lastExpressionChange = millis();
}

void loop() {
    eyes.update();

    const unsigned long now = millis();
    if (now - lastExpressionChange >= EXPRESSION_HOLD_MS) {
        lastExpressionChange = now;
        expressionIndex = (expressionIndex + 1) % EXPRESSION_COUNT;
        eyes.setExpression(EXPRESSIONS[expressionIndex]);
    }
}
