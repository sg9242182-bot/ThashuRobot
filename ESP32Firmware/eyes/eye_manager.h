#pragma once

#include <stdint.h>
#include <Adafruit_SSD1306.h>

class EyeManager {
public:
    EyeManager();

    enum Expression : uint8_t {
        IDLE = 0,
        HAPPY,
        SAD,
        ANGRY,
        CURIOUS,
        SLEEPY,
        WINK,
        SURPRISED,
        CONFUSED,
        LOVE,
        BLINK,
        EXPRESSION_COUNT,
    };

    bool begin(uint8_t leftAddress = 0x3C, uint8_t rightAddress = 0x3D);
    void update();
    void setExpression(Expression expression);
    Expression getExpression() const;
    bool isReady() const;

private:
    static constexpr uint8_t SCREEN_WIDTH = 128;
    static constexpr uint8_t SCREEN_HEIGHT = 64;
    static constexpr uint8_t SDA_PIN = 21;
    static constexpr uint8_t SCL_PIN = 22;
    static constexpr uint16_t FRAME_INTERVAL_MS = 35;
    static constexpr uint8_t STROKE = 5;

    Adafruit_SSD1306 leftDisplay;
    Adafruit_SSD1306 rightDisplay;

    bool ready = false;
    Expression expression = IDLE;
    Expression returnExpression = IDLE;
    uint8_t animationFrame = 0;
    unsigned long lastFrameTime = 0;
    bool blinkActive = false;

    void render();
    void drawExpression(Adafruit_SSD1306& display, bool leftEye);
    void drawIdle(Adafruit_SSD1306& display, bool leftEye);
    void drawHappy(Adafruit_SSD1306& display);
    void drawSad(Adafruit_SSD1306& display, bool leftEye);
    void drawAngry(Adafruit_SSD1306& display, bool leftEye);
    void drawCurious(Adafruit_SSD1306& display, bool leftEye);
    void drawSleepy(Adafruit_SSD1306& display, bool leftEye);
    void drawWink(Adafruit_SSD1306& display, bool leftEye);
    void drawSurprised(Adafruit_SSD1306& display);
    void drawConfused(Adafruit_SSD1306& display, bool leftEye);
    void drawLove(Adafruit_SSD1306& display);
    void drawBlink(Adafruit_SSD1306& display);

    void drawArc(Adafruit_SSD1306& display, int16_t cx, int16_t cy,
                 int16_t radiusX, int16_t radiusY, int16_t startDeg,
                 int16_t endDeg, uint8_t thickness = STROKE);
    void drawThickLine(Adafruit_SSD1306& display, int16_t x0, int16_t y0,
                       int16_t x1, int16_t y1, uint8_t thickness = STROKE);
    void drawFilledEye(Adafruit_SSD1306& display, int16_t cx, int16_t cy,
                       int16_t rx, int16_t ry);
    void drawHighlight(Adafruit_SSD1306& display, int16_t x, int16_t y);
};
