#include "eye_manager.h"

#include <Wire.h>
#include <math.h>

namespace {
constexpr float PI_F = 3.14159265f;
}

EyeManager::EyeManager()
    : leftDisplay(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1),
      rightDisplay(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1) {}

bool EyeManager::begin(uint8_t leftAddress, uint8_t rightAddress) {
    Wire.begin(SDA_PIN, SCL_PIN);

    if (!leftDisplay.begin(SSD1306_SWITCHCAPVCC, leftAddress)) {
        return false;
    }
    if (!rightDisplay.begin(SSD1306_SWITCHCAPVCC, rightAddress)) {
        return false;
    }

    ready = true;
    expression = IDLE;
    returnExpression = IDLE;
    animationFrame = 0;
    blinkActive = false;
    lastFrameTime = millis();
    render();
    return true;
}

void EyeManager::update() {
    if (!ready || !blinkActive) {
        return;
    }

    const unsigned long now = millis();
    if (now - lastFrameTime < FRAME_INTERVAL_MS) {
        return;
    }

    lastFrameTime = now;
    ++animationFrame;

    if (animationFrame >= 7) {
        blinkActive = false;
        expression = returnExpression;
        animationFrame = 0;
    }

    render();
}

void EyeManager::setExpression(Expression newExpression) {
    if (!ready || newExpression >= EXPRESSION_COUNT) {
        return;
    }

    if (newExpression == BLINK) {
        returnExpression = expression;
        blinkActive = true;
        animationFrame = 0;
        lastFrameTime = millis();
        render();
        return;
    }

    blinkActive = false;
    expression = newExpression;
    returnExpression = newExpression;
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
    if (blinkActive) {
        drawBlink(display);
        return;
    }

    switch (expression) {
        case IDLE:      drawIdle(display, leftEye); break;
        case HAPPY:     drawHappy(display); break;
        case SAD:       drawSad(display, leftEye); break;
        case ANGRY:     drawAngry(display, leftEye); break;
        case CURIOUS:   drawCurious(display, leftEye); break;
        case SLEEPY:    drawSleepy(display, leftEye); break;
        case WINK:      drawWink(display, leftEye); break;
        case SURPRISED: drawSurprised(display); break;
        case CONFUSED:  drawConfused(display, leftEye); break;
        case LOVE:      drawLove(display); break;
        default:        drawIdle(display, leftEye); break;
    }
}

void EyeManager::drawIdle(Adafruit_SSD1306& display, bool leftEye) {
    const int16_t cx = 64;
    const int16_t cy = 34;

    // Cute filled robot-eye silhouette. No human-style outline and no round pupil.
    drawFilledEye(display, cx, cy, 22, 25);

    // Small rectangular shine makes the eye read as a character rather than an eyeball.
    drawHighlight(display, leftEye ? 54 : 54, 24);

    // Small vertical cutout gives the idle eye a friendly, focused look.
    display.fillRoundRect(61, 38, 7, 11, 3, SSD1306_BLACK);
}

void EyeManager::drawHappy(Adafruit_SSD1306& display) {
    // Thick upward arch: the primary happy-eye shape from the reference style.
    drawArc(display, 64, 38, 34, 25, 200, 340, 6);
}

void EyeManager::drawSad(Adafruit_SSD1306& display, bool leftEye) {
    // Drooping upper lid plus a small lower accent. Both eyes are mirrored in placement.
    drawArc(display, 64, 26, 34, 22, 25, 155, 5);
    display.fillCircle(64, 46, 5, SSD1306_WHITE);

    if (leftEye) {
        drawThickLine(display, 34, 15, 58, 22, 4);
    } else {
        drawThickLine(display, 94, 15, 70, 22, 4);
    }
}

void EyeManager::drawAngry(Adafruit_SSD1306& display, bool leftEye) {
    // Exact mirror geometry for left/right eyes.
    if (leftEye) {
        drawThickLine(display, 25, 19, 95, 35, 7);
    } else {
        drawThickLine(display, 103, 19, 33, 35, 7);
    }

    display.fillRoundRect(59, 38, 10, 10, 4, SSD1306_WHITE);
}

void EyeManager::drawCurious(Adafruit_SSD1306& display, bool leftEye) {
    drawFilledEye(display, 64, 34, 19, 23);

    // Pupil is a cutout slot rather than a generic black circle.
    const int16_t x = leftEye ? 57 : 67;
    display.fillRoundRect(x, 28, 9, 15, 4, SSD1306_BLACK);
    drawHighlight(display, x + 2, 26);

    if (leftEye) {
        drawArc(display, 64, 18, 29, 10, 200, 340, 4);
    } else {
        drawArc(display, 64, 18, 29, 10, 200, 340, 4);
    }
}

void EyeManager::drawSleepy(Adafruit_SSD1306& display, bool leftEye) {
    drawThickLine(display, 29, 35, 44, 31, 5);
    drawThickLine(display, 44, 31, 64, 33, 5);
    drawThickLine(display, 64, 33, 84, 31, 5);
    drawThickLine(display, 84, 31, 99, 35, 5);

    if (!leftEye) {
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(94, 9);
        display.print('z');
        display.setCursor(104, 1);
        display.print('z');
    }
}

void EyeManager::drawWink(Adafruit_SSD1306& display, bool leftEye) {
    if (leftEye) {
        drawHappy(display);
        return;
    }

    drawFilledEye(display, 64, 34, 20, 23);
    display.fillRoundRect(60, 27, 9, 15, 4, SSD1306_BLACK);
    drawHighlight(display, 57, 24);
}

void EyeManager::drawSurprised(Adafruit_SSD1306& display) {
    // Tall rounded eye with a narrow cutout, not a white circle with a black pupil.
    drawFilledEye(display, 64, 34, 18, 25);
    display.fillRoundRect(59, 20, 10, 28, 5, SSD1306_BLACK);
    display.fillRect(61, 24, 6, 8, SSD1306_WHITE);
}

void EyeManager::drawConfused(Adafruit_SSD1306& display, bool leftEye) {
    drawFilledEye(display, 64, 36, 19, 20);

    const int16_t cutoutX = leftEye ? 56 : 68;
    display.fillRoundRect(cutoutX, 31, 10, 12, 4, SSD1306_BLACK);
    drawHighlight(display, cutoutX + 1, 28);

    if (leftEye) {
        drawThickLine(display, 33, 17, 59, 12, 4);
    } else {
        drawThickLine(display, 95, 17, 69, 12, 4);
    }
}

void EyeManager::drawLove(Adafruit_SSD1306& display) {
    display.fillCircle(53, 29, 10, SSD1306_WHITE);
    display.fillCircle(75, 29, 10, SSD1306_WHITE);
    display.fillTriangle(43, 34, 85, 34, 64, 56, SSD1306_WHITE);
}

void EyeManager::drawBlink(Adafruit_SSD1306& display) {
    switch (animationFrame) {
        case 0:
            drawIdle(display, false);
            break;
        case 1:
            drawArc(display, 64, 36, 30, 18, 200, 340, 5);
            break;
        case 2:
        case 3:
        case 4:
            drawThickLine(display, 31, 34, 97, 34, 6);
            break;
        case 5:
            drawArc(display, 64, 36, 30, 18, 200, 340, 5);
            break;
        default:
            drawIdle(display, false);
            break;
    }
}

void EyeManager::drawArc(Adafruit_SSD1306& display,
                         int16_t cx,
                         int16_t cy,
                         int16_t radiusX,
                         int16_t radiusY,
                         int16_t startDeg,
                         int16_t endDeg,
                         uint8_t thickness) {
    for (int16_t deg = startDeg; deg <= endDeg; ++deg) {
        const float rad = deg * PI_F / 180.0f;
        const int16_t x = cx + static_cast<int16_t>(cosf(rad) * radiusX);
        const int16_t y = cy + static_cast<int16_t>(sinf(rad) * radiusY);

        for (int16_t t = -static_cast<int16_t>(thickness) / 2;
             t <= static_cast<int16_t>(thickness) / 2; ++t) {
            display.drawPixel(x, y + t, SSD1306_WHITE);
        }
    }
}

void EyeManager::drawThickLine(Adafruit_SSD1306& display,
                               int16_t x0,
                               int16_t y0,
                               int16_t x1,
                               int16_t y1,
                               uint8_t thickness) {
    const int16_t half = thickness / 2;
    for (int16_t i = -half; i <= half; ++i) {
        display.drawLine(x0, y0 + i, x1, y1 + i, SSD1306_WHITE);
    }
}

void EyeManager::drawFilledEye(Adafruit_SSD1306& display,
                               int16_t cx,
                               int16_t cy,
                               int16_t rx,
                               int16_t ry) {
    display.fillRoundRect(cx - rx, cy - ry, rx * 2, ry * 2, rx / 2, SSD1306_WHITE);
}

void EyeManager::drawHighlight(Adafruit_SSD1306& display, int16_t x, int16_t y) {
    display.fillRect(x, y, 5, 5, SSD1306_BLACK);
}
