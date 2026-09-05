#include "eye_manager.h"

#include <Wire.h>

namespace {
constexpr int16_t CENTER_X = 64;
constexpr int16_t CENTER_Y = 34;
constexpr int16_t EYE_LEFT = 25;
constexpr int16_t EYE_RIGHT = 103;
constexpr int16_t EYE_TOP = 13;
constexpr int16_t EYE_BOTTOM = 54;
constexpr int16_t PUPIL_RADIUS = 7;
}

EyeManager::EyeManager()
    : leftDisplay(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1),
      rightDisplay(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1) {}

bool EyeManager::begin(uint8_t leftAddress, uint8_t rightAddress) {
    Wire.begin(SDA_PIN, SCL_PIN);

    if (!leftDisplay.begin(SSD1306_SWITCHCAPVCC, leftAddress)) {
        ready = false;
        return false;
    }

    if (!rightDisplay.begin(SSD1306_SWITCHCAPVCC, rightAddress)) {
        ready = false;
        return false;
    }

    leftDisplay.clearDisplay();
    rightDisplay.clearDisplay();
    leftDisplay.display();
    rightDisplay.display();

    ready = true;
    expression = IDLE;
    animationFrame = 0;
    lastFrameTime = millis();
    render();
    return true;
}

void EyeManager::update() {
    if (!ready) {
        return;
    }

    const unsigned long now = millis();
    if (now - lastFrameTime < FRAME_INTERVAL_MS) {
        return;
    }

    lastFrameTime = now;

    // Only BLINK has an animation sequence. All other expressions remain
    // stable until a new serial/application command calls setExpression().
    if (expression == BLINK) {
        animationFrame++;
        render();
    }
}

void EyeManager::setExpression(Expression newExpression) {
    if (newExpression >= EXPRESSION_COUNT) {
        return;
    }

    expression = newExpression;
    animationFrame = 0;
    render();
}

EyeManager::Expression EyeManager::getExpression() const {
    return expression;
}

bool EyeManager::isReady() const {
    return ready;
}

void EyeManager::render() {
    leftDisplay.clearDisplay();
    rightDisplay.clearDisplay();

    drawExpression(leftDisplay, true);
    drawExpression(rightDisplay, false);

    leftDisplay.display();
    rightDisplay.display();
}

void EyeManager::drawExpression(Adafruit_SSD1306& display, bool leftEye) {
    switch (expression) {
        case IDLE:
            drawIdleEye(display);
            break;

        case HAPPY:
            drawHappyEye(display);
            break;

        case SAD:
            drawSadEye(display);
            break;

        case ANGRY:
            drawAngryEye(display, leftEye);
            break;

        case CURIOUS:
            drawCuriousEye(display, leftEye);
            break;

        case SLEEPY:
            drawSleepyEye(display);
            break;

        case WINK:
            drawWinkEye(display, leftEye);
            break;

        case SURPRISED:
            drawSurprisedEye(display);
            break;

        case CONFUSED:
            drawConfusedEye(display, leftEye);
            break;

        case LOVE:
            drawHeart(display);
            break;

        case BLINK:
            drawBlinkEye(display);
            break;

        default:
            drawIdleEye(display);
            break;
    }
}

void EyeManager::drawIdleEye(Adafruit_SSD1306& display) {
    // Soft, slightly rounded almond rather than a rectangle or circular eye.
    display.drawLine(32, 26, 45, 18, SSD1306_WHITE);
    display.drawLine(45, 18, 64, 15, SSD1306_WHITE);
    display.drawLine(64, 15, 83, 18, SSD1306_WHITE);
    display.drawLine(83, 18, 96, 26, SSD1306_WHITE);
    display.drawLine(32, 42, 45, 50, SSD1306_WHITE);
    display.drawLine(45, 50, 64, 53, SSD1306_WHITE);
    display.drawLine(64, 53, 83, 50, SSD1306_WHITE);
    display.drawLine(83, 50, 96, 42, SSD1306_WHITE);
    display.fillCircle(CENTER_X, CENTER_Y, PUPIL_RADIUS, SSD1306_WHITE);
    display.fillCircle(CENTER_X, CENTER_Y, 3, SSD1306_BLACK);
}

void EyeManager::drawHappyEye(Adafruit_SSD1306& display) {
    // Thick upward-curving closed eye, matching the reference's cute style.
    drawThickLine(display, 30, 39, 42, 27, 4);
    drawThickLine(display, 42, 27, 55, 22, 4);
    drawThickLine(display, 55, 22, 64, 21, 4);
    drawThickLine(display, 64, 21, 73, 22, 4);
    drawThickLine(display, 73, 22, 86, 27, 4);
    drawThickLine(display, 86, 27, 98, 39, 4);
}

void EyeManager::drawSadEye(Adafruit_SSD1306& display) {
    // Drooping upper lid with a small expressive pupil, not a generic oval.
    drawThickLine(display, 30, 24, 45, 30, 3);
    drawThickLine(display, 45, 30, 64, 34, 3);
    drawThickLine(display, 64, 34, 83, 30, 3);
    drawThickLine(display, 83, 30, 98, 24, 3);
    display.fillCircle(64, 39, 6, SSD1306_WHITE);
    drawBrow(display, 34, 15, 58, 23, 3);
}

void EyeManager::drawAngryEye(Adafruit_SSD1306& display, bool leftEye) {
    // Strong slanted upper lid; the two eyes mirror each other.
    if (leftEye) {
        drawThickLine(display, 27, 19, 99, 34, 5);
        display.fillCircle(64, 40, 7, SSD1306_WHITE);
    } else {
        drawThickLine(display, 101, 19, 29, 34, 5);
        display.fillCircle(64, 40, 7, SSD1306_WHITE);
    }
}

void EyeManager::drawCuriousEye(Adafruit_SSD1306& display, bool leftEye) {
    // Large asymmetric-looking eye with the pupil shifted inward.
    display.drawCircle(CENTER_X, 34, 19, SSD1306_WHITE);
    display.drawCircle(CENTER_X, 34, 20, SSD1306_WHITE);
    display.fillCircle(leftEye ? 58 : 70, 35, 7, SSD1306_WHITE);
    display.fillCircle(leftEye ? 58 : 70, 35, 3, SSD1306_BLACK);
    drawBrow(display, leftEye ? 35 : 51, 14, leftEye ? 60 : 94, 10, 3);
}

void EyeManager::drawSleepyEye(Adafruit_SSD1306& display) {
    drawThickLine(display, 30, 32, 45, 29, 4);
    drawThickLine(display, 45, 29, 64, 30, 4);
    drawThickLine(display, 64, 30, 83, 29, 4);
    drawThickLine(display, 83, 29, 98, 32, 4);
}

void EyeManager::drawWinkEye(Adafruit_SSD1306& display, bool leftEye) {
    if (leftEye) {
        drawHappyEye(display);
        return;
    }

    display.drawCircle(CENTER_X, CENTER_Y, 18, SSD1306_WHITE);
    display.fillCircle(CENTER_X, CENTER_Y, 7, SSD1306_BLACK);
    display.fillCircle(CENTER_X - 3, CENTER_Y - 3, 3, SSD1306_WHITE);
}

void EyeManager::drawSurprisedEye(Adafruit_SSD1306& display) {
    // Vertical surprised eye, avoiding the plain round pupil design.
    display.fillRoundRect(46, 11, 36, 46, 15, SSD1306_WHITE);
    display.fillRoundRect(57, 20, 14, 28, 7, SSD1306_BLACK);
}

void EyeManager::drawConfusedEye(Adafruit_SSD1306& display, bool leftEye) {
    display.drawCircle(CENTER_X, 36, 16, SSD1306_WHITE);
    display.fillCircle(leftEye ? 60 : 68, 35, 6, SSD1306_BLACK);
    drawBrow(display, leftEye ? 34 : 70, leftEye ? 12 : 17,
              leftEye ? 58 : 96, leftEye ? 17 : 12, 3);
}

void EyeManager::drawHeart(Adafruit_SSD1306& display) {
    display.fillCircle(54, 29, 11, SSD1306_WHITE);
    display.fillCircle(74, 29, 11, SSD1306_WHITE);
    display.fillTriangle(43, 34, 85, 34, 64, 55, SSD1306_WHITE);
}

void EyeManager::drawBlinkEye(Adafruit_SSD1306& display) {
    // 8-frame close/open sequence. It only advances while BLINK is selected.
    const uint8_t phase = animationFrame % 8;

    if (phase == 0 || phase == 7) {
        drawIdleEye(display);
    } else if (phase == 1 || phase == 6) {
        drawThickLine(display, 30, 34, 98, 34, 4);
    } else if (phase == 2 || phase == 5) {
        drawThickLine(display, 32, 32, 96, 32, 4);
    } else {
        drawThickLine(display, 34, 30, 94, 30, 4);
    }
}

void EyeManager::drawThickLine(Adafruit_SSD1306& display,
                               int16_t x0,
                               int16_t y0,
                               int16_t x1,
                               int16_t y1,
                               uint8_t thickness) {
    const int16_t offset = thickness / 2;
    for (int16_t i = -offset; i <= offset; ++i) {
        display.drawLine(x0, y0 + i, x1, y1 + i, SSD1306_WHITE);
    }
}

void EyeManager::drawBrow(Adafruit_SSD1306& display,
                          int16_t x0,
                          int16_t y0,
                          int16_t x1,
                          int16_t y1,
                          uint8_t thickness) {
    drawThickLine(display, x0, y0, x1, y1, thickness);
}
