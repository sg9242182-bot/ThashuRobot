#ifndef EYE_MANAGER_H
#define EYE_MANAGER_H

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Shared I2C Pins matching THASHU_ESP32_PIN_ALLOCATION.md
#define OLED_ADDR         0x3C
#define OLED_LEFT_MUX_CHANNEL  6
#define OLED_RIGHT_MUX_CHANNEL 7

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

// Per-display pose parameters; the two eyes intentionally use different poses.
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

    bool begin();
    bool isReady() const;
    void update();

    void setExpression(Expression expr);
    void triggerBlink();

    void handleCommand(const char *cmd);
    void printHelp();

  private:
    // Both displays use address 0x3C but have isolated mux channels and buffers.
    Adafruit_SSD1306 _leftDisplay;
    Adafruit_SSD1306 _rightDisplay;

    EyeParams _currentParams[2];
    EyeParams _fromParams[2];
    EyeParams _toParams[2];

    unsigned long _transitionStartMs;
    unsigned long _transitionDurationMs;
    Expression    _currentTarget;

    bool          _blinkActive[2];
    unsigned long _blinkStartMs[2];
    unsigned long _blinkDurationMs;
    bool          _renderDirty;
    bool          _ready = false;
    unsigned long _lastHealthCheckMs = 0;
    unsigned long _nextAutoBlinkMs = 0;

    EyeParams computeExpressionParams(Expression expr, uint8_t eyeIndex);
    EyeParams getInterpolatedParams(unsigned long now, uint8_t eyeIndex);
    float     getBlinkAmount(unsigned long now, uint8_t eyeIndex);
    bool      renderFrame(const EyeParams &left, float leftBlink,
                          const EyeParams &right, float rightBlink);
    void      renderEye(Adafruit_SSD1306 &display, const EyeParams &p,
                        float blinkAmt, bool leftEye);
    void      drawHeart(Adafruit_SSD1306 &display, int16_t cx, int16_t cy,
                        float scale);

    static float easeInOutCubic(float t);
};

#endif // EYE_MANAGER_H
