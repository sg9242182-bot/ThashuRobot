#pragma once

#include <stdint.h>
#include <Adafruit_SSD1306.h>

class EyeManager {
public:
    enum Expression : uint8_t {
        HAPPY = 0,
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
    Expression expression = HAPPY;
    uint8_t animationFrame = 0;
    unsigned long lastFrameTime = 0;

    void render();
    void drawExpression(Adafruit_SSD1306& display, bool leftEye);
    void drawOpenEye(Adafruit_SSD1306& display, int16_t pupilOffsetX, int16_t pupilOffsetY,
                     uint8_t openness = 0);
    void drawClosedEye(Adafruit_SSD1306& display, bool happyCurve);
    void drawHeart(Adafruit_SSD1306& display);
    void drawBrow(Adafruit_SSD1306& display, int16_t x0, int16_t y0,
                  int16_t x1, int16_t y1);
};
