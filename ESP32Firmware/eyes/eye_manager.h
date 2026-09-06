#ifndef EYE_MANAGER_H
#define EYE_MANAGER_H

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Shared I2C Pins matching THASHU_ESP32_PIN_ALLOCATION.md
#define OLED_SDA_PIN      21
#define OLED_SCL_PIN      22
#define OLED_ADDR         0x3C

#define OLED_WIDTH        128
#define OLED_HEIGHT       64
#define OLED_RESET_PIN    -1

enum Expression {
  EXPR_IDLE = 0,
  EXPR_HAPPY,
  EXPR_SAD,
  EXPR_ANGRY,
  EXPR_CURIOUS,
  EXPR_SLEEPY,
  EXPR_SURPRISED,
  EXPR_LOVE,
  EXPR_COUNT
};

// Symmetrical pose parameters
struct EyeParams {
  float w;          // Eye width
  float h;          // Eye height
  float cy;         // Vertical center offset
  float corner;     // Corner radius of the eye block
  float topCut;     // Top eyelid downward cut
  float botCut;     // Bottom eyelid upward cut
  float smileCurve; // Curved smile mask amount (0.0 to 1.0)
  float heartScale; // Heart shape amount (0.0 to 1.0)
};

class EyeManager {
  public:
    EyeManager();

    void begin();
    void update();

    void setExpression(Expression expr);
    void triggerBlink();

    void handleCommand(const char *cmd);
    void printHelp();

  private:
    // Both physical OLEDs intentionally share 0x3C and display the same symmetric eye.
    Adafruit_SSD1306 _display;

    EyeParams _currentParams;
    EyeParams _fromParams;
    EyeParams _toParams;

    unsigned long _transitionStartMs;
    unsigned long _transitionDurationMs;
    Expression    _currentTarget;

    bool          _blinkActive;
    unsigned long _blinkStartMs;
    unsigned long _blinkDurationMs;
    bool          _renderDirty;

    EyeParams computeExpressionParams(Expression expr);
    EyeParams getInterpolatedParams(unsigned long now);
    float     getBlinkAmount(unsigned long now);
    void      renderFrame(const EyeParams &p, float blinkAmt);
    void      drawHeart(int16_t cx, int16_t cy, float scale);

    static float easeInOutCubic(float t);
};

#endif // EYE_MANAGER_H