#pragma once

#include <stdint.h>
#include <Adafruit_SSD1306.h>

class EyeManager {
public:
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
    static constexpr uint16_t FRAME_INTERVAL_MS = 50;

    Adafruit_SSD1306 leftDisplay;
    Adafruit_SSD1306 rightDisplay;

    bool ready = false;
    Expression expression = IDLE;
    uint8_t animationFrame = 0;
    unsigned long lastFrameTime = 0;

    void render();
    void drawExpression(Adafruit_SSD1306& display, bool leftEye);

    void drawIdleEye(Adafruit_SSD1306& display);
    void drawHappyEye(Adafruit_SSD1306& display);
    void drawSadEye(Adafruit_SSD1306& display);
    void drawAngryEye(Adafruit_SSD1306& display, bool leftEye);
    void drawCuriousEye(Adafruit_SSD1306& display, bool leftEye);
    void drawSleepyEye(Adafruit_SSD1306& display);
    void drawWinkEye(Adafruit_SSD1306& display, bool leftEye);
    void drawSurprisedEye(Adafruit_SSD1306& display);
    void drawConfusedEye(Adafruit_SSD1306& display, bool leftEye);
    void drawHeart(Adafruit_SSD1306& display);
    void drawBlinkEye(Adafruit_SSD1306& display);

    void drawThickLine(Adafruit_SSD1306& display, int16_t x0, int16_t y0,
                       int16_t x1, int16_t y1, uint8_t thickness);
    void drawBrow(Adafruit_SSD1306& display, int16_t x0, int16_t y0,
                  int16_t x1, int16_t y1, uint8_t thickness = 3);
};
