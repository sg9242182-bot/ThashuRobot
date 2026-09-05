#pragma once

#include <Arduino.h>
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
        EXPRESSION_COUNT
    };

    bool begin(uint8_t leftAddress = 0x3C, uint8_t rightAddress = 0x3D);
    void update();
    void setExpression(Expression expression);
    Expression getExpression() const;
    bool isReady() const;

private:
    static constexpr uint8_t WIDTH = 128;
    static constexpr uint8_t HEIGHT = 64;
    static constexpr uint8_t SDA_PIN = 21;
    static constexpr uint8_t SCL_PIN = 22;
    static constexpr uint16_t TRANSITION_MS = 220;
    static constexpr uint16_t FRAME_MS = 25;
    static constexpr uint16_t BLINK_FRAME_MS = 30;

    struct Pose {
        float openness;
        float width;
        float height;
        float pupilX;
        float pupilY;
        float pupilWidth;
        float pupilHeight;
        float upperLid;
        float lowerLid;
        float brow;
        float browTilt;
    };

    Adafruit_SSD1306 leftDisplay;
    Adafruit_SSD1306 rightDisplay;

    bool ready = false;
    Expression currentExpression = IDLE;
    Expression targetExpression = IDLE;
    Expression blinkReturnExpression = IDLE;
    Pose currentPose{};
    Pose startPose{};
    Pose targetPose{};
    bool transitioning = false;
    bool blinkActive = false;
    uint8_t blinkFrame = 0;
    unsigned long transitionStart = 0;
    unsigned long lastFrame = 0;

    Pose poseFor(Expression expression) const;
    static Pose interpolate(const Pose& a, const Pose& b, float t);
    static float easeInOut(float t);

    void render();
    void renderEye(Adafruit_SSD1306& display, bool leftEye, const Pose& pose);
    void renderBlink(Adafruit_SSD1306& display, bool leftEye);
    void drawBaseEye(Adafruit_SSD1306& display, const Pose& pose);
    void drawPupil(Adafruit_SSD1306& display, const Pose& pose);
    void drawLids(Adafruit_SSD1306& display, const Pose& pose, bool leftEye);
    void drawBrow(Adafruit_SSD1306& display, const Pose& pose, bool leftEye);
    void drawLoveMark(Adafruit_SSD1306& display);

    void fillOrganicEye(Adafruit_SSD1306& display, int16_t cx, int16_t cy,
                        int16_t halfWidth, int16_t halfHeight, float openness);
    void eraseLid(Adafruit_SSD1306& display, int16_t cx, int16_t cy,
                  int16_t halfWidth, int16_t halfHeight, float amount,
                  bool upper, bool leftEye);

    void drawThickLine(Adafruit_SSD1306& display, int16_t x0, int16_t y0,
                       int16_t x1, int16_t y1, uint8_t thickness);
};
