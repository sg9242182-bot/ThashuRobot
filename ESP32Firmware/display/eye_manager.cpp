#include "eye_manager.h"

#include <Wire.h>

namespace {
constexpr int16_t EYE_CENTER_X = 64;
constexpr int16_t EYE_CENTER_Y = 34;
constexpr int16_t EYE_RADIUS_X = 38;
constexpr int16_t EYE_RADIUS_Y = 25;
constexpr int16_t PUPIL_RADIUS = 10;
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
    animationFrame++;
    render();
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
    const bool winkLeft = leftEye;
    const bool winkRight = !leftEye;

    switch (expression) {
        case HAPPY:
            drawClosedEye(display, true);
            break;

        case SAD:
            drawOpenEye(display, 0, 2);
            drawBrow(display, 31, 15, 59, 22);
            break;

        case ANGRY:
            drawOpenEye(display, 0, 1);
            if (leftEye) {
                drawBrow(display, 28, 14, 60, 25);
            } else {
                drawBrow(display, 68, 25, 100, 14);
            }
            break;

        case CURIOUS:
            drawOpenEye(display, leftEye ? 5 : -5, -2);
            display.drawLine(32, 13, 56, 10, SSD1306_WHITE);
            break;

        case SLEEPY:
            display.fillRoundRect(24, 29, 80, 16, 8, SSD1306_WHITE);
            display.fillRect(24, 29, 80, 8, SSD1306_BLACK);
            if (!leftEye) {
                display.setTextSize(1);
                display.setTextColor(SSD1306_WHITE);
                display.setCursor(92, 8);
                display.print("z");
                display.setCursor(101, 2);
                display.print("z");
            }
            break;

        case WINK:
            if (winkLeft) {
                drawClosedEye(display, true);
            } else {
                drawOpenEye(display, 0, 0);
            }
            break;

        case SURPRISED:
            display.fillCircle(EYE_CENTER_X, EYE_CENTER_Y, 22, SSD1306_WHITE);
            display.fillCircle(EYE_CENTER_X, EYE_CENTER_Y, 9, SSD1306_BLACK);
            break;

        case CONFUSED:
            drawOpenEye(display, leftEye ? 3 : -3, 0);
            if (leftEye) {
                drawBrow(display, 30, 15, 58, 11);
            } else {
                drawBrow(display, 70, 11, 98, 16);
            }
            break;

        case LOVE:
            drawHeart(display);
            break;

        case BLINK: {
            const uint8_t phase = animationFrame % 8;
            if (phase == 0 || phase == 7) {
                drawOpenEye(display, 0, 0);
            } else if (phase == 1 || phase == 6) {
                drawOpenEye(display, 0, 0, 10);
            } else {
                drawClosedEye(display, false);
            }
            break;
        }

        default:
            drawOpenEye(display, 0, 0);
            break;
    }
}

void EyeManager::drawOpenEye(Adafruit_SSD1306& display,
                             int16_t pupilOffsetX,
                             int16_t pupilOffsetY,
                             uint8_t openness) {
    const int16_t radiusY = EYE_RADIUS_Y - openness;
    display.fillRoundRect(EYE_CENTER_X - EYE_RADIUS_X,
                          EYE_CENTER_Y - radiusY,
                          EYE_RADIUS_X * 2,
                          radiusY * 2,
                          18,
                          SSD1306_WHITE);

    display.fillCircle(EYE_CENTER_X + pupilOffsetX,
                       EYE_CENTER_Y + pupilOffsetY,
                       PUPIL_RADIUS,
                       SSD1306_BLACK);
}

void EyeManager::drawClosedEye(Adafruit_SSD1306& display, bool happyCurve) {
    if (happyCurve) {
        display.drawArc(EYE_CENTER_X, EYE_CENTER_Y + 7, 31, 18, 200, 340, SSD1306_WHITE);
        display.drawLine(48, 51, 80, 51, SSD1306_WHITE);
    } else {
        display.drawLine(28, 36, 100, 36, SSD1306_WHITE);
    }
}

void EyeManager::drawHeart(Adafruit_SSD1306& display) {
    display.fillCircle(54, 30, 12, SSD1306_WHITE);
    display.fillCircle(74, 30, 12, SSD1306_WHITE);
    display.fillTriangle(42, 34, 86, 34, 64, 55, SSD1306_WHITE);
}

void EyeManager::drawBrow(Adafruit_SSD1306& display,
                          int16_t x0,
                          int16_t y0,
                          int16_t x1,
                          int16_t y1) {
    display.drawLine(x0, y0, x1, y1, SSD1306_WHITE);
    display.drawLine(x0, y0 + 1, x1, y1 + 1, SSD1306_WHITE);
}
