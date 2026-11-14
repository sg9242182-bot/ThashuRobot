#include "eye_manager.h"
#include "i2c_mux.h"
#include <math.h>

EyeManager::EyeManager()
: _leftDisplay(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET_PIN),
  _rightDisplay(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET_PIN),
  _transitionStartMs(0),
  _transitionDurationMs(1),
  _currentTarget(EXPR_IDLE),
  _blinkDurationMs(360),
  _renderDirty(true),
  _ready(false) {

  _blinkActive[0] = false;
  _blinkActive[1] = false;
  _blinkStartMs[0] = 0;
  _blinkStartMs[1] = 0;
  for (uint8_t eye = 0; eye < 2; ++eye) {
    _currentParams[eye] = computeExpressionParams(EXPR_IDLE, eye);
    _fromParams[eye] = _currentParams[eye];
    _toParams[eye] = _currentParams[eye];
  }
}

bool EyeManager::begin() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);

  bool leftReady = selectI2cMuxChannel(OLED_LEFT_MUX_CHANNEL);
  if (leftReady) leftReady = _leftDisplay.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  const bool leftMuxReady = deselectI2cMux();

  bool rightReady = selectI2cMuxChannel(OLED_RIGHT_MUX_CHANNEL);
  if (rightReady) rightReady = _rightDisplay.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  const bool rightMuxReady = deselectI2cMux();
  _ready = leftReady && rightReady && leftMuxReady && rightMuxReady;
  if (!_ready) return false;
  _nextAutoBlinkMs = millis() + 2500;
  _leftDisplay.clearDisplay();
  _rightDisplay.clearDisplay();
  if (!renderFrame(_currentParams[0], 0.0f, _currentParams[1], 0.0f)) return false;
  _renderDirty = false;
  return true;
}

bool EyeManager::isReady() const { return _ready; }

void EyeManager::update() {
  static unsigned long lastFrameMs = 0;
  const unsigned long now = millis();
  if ((long)(now - _nextAutoBlinkMs) >= 0) {
    triggerBlink();
    Serial.println(F("DBG|EYES|AUTO_BLINK"));
    _nextAutoBlinkMs = now + 3500;
  }
  if (now - _lastHealthCheckMs >= 500) {
    _lastHealthCheckMs = now;
    bool leftReady = selectI2cMuxChannel(OLED_LEFT_MUX_CHANNEL);
    if (leftReady) {
      Wire.beginTransmission(OLED_ADDR);
      leftReady = Wire.endTransmission() == 0;
    }
    const bool leftMuxReady = deselectI2cMux();

    bool rightReady = selectI2cMuxChannel(OLED_RIGHT_MUX_CHANNEL);
    if (rightReady) {
      Wire.beginTransmission(OLED_ADDR);
      rightReady = Wire.endTransmission() == 0;
    }
    const bool rightMuxReady = deselectI2cMux();
    _ready = leftReady && rightReady && leftMuxReady && rightMuxReady;
  }

  const bool transitionActive = (now - _transitionStartMs) < _transitionDurationMs;
  const bool blinkWasActive = _blinkActive[0] || _blinkActive[1];

  // If nothing is animating and the last requested frame is already on the OLED,
  // do not retransmit the framebuffer. This keeps the shared I2C bus available.
  if (!transitionActive && !blinkWasActive && !_renderDirty) return;

  // Each eye needs its own I2C transfer, so cap animated frames at 20 FPS.
  // A dirty settled frame still commits after a transition completes.
  if ((now - lastFrameMs < 50) && (transitionActive || blinkWasActive)) return;
  lastFrameMs = now;

  _currentParams[0] = getInterpolatedParams(now, 0);
  _currentParams[1] = getInterpolatedParams(now, 1);
  const float leftBlink = getBlinkAmount(now, 0);
  const float rightBlink = getBlinkAmount(now, 1);

  _ready = renderFrame(_currentParams[0], leftBlink,
                       _currentParams[1], rightBlink);

  // If getBlinkAmount() completed the blink during this frame, this render is the
  // final open frame. If the expression transition also finished, the target pose
  // is now committed and the module can remain idle until the next command.
  const bool transitionStillActive = (now - _transitionStartMs) < _transitionDurationMs;
  if (!transitionStillActive && !_blinkActive[0] && !_blinkActive[1]) {
    _renderDirty = false;
  }
}

void EyeManager::setExpression(Expression expr) {
  const unsigned long now = millis();
  for (uint8_t eye = 0; eye < 2; ++eye) {
    _fromParams[eye] = getInterpolatedParams(now, eye);
    _toParams[eye] = computeExpressionParams(expr, eye);
  }
  _transitionStartMs = now;
  _transitionDurationMs = 250;
  _currentTarget = expr;
  _renderDirty = true;
}

void EyeManager::triggerBlink() {
  if (_blinkActive[0] || _blinkActive[1]) return;
  const unsigned long now = millis();
  _blinkActive[0] = true;
  _blinkActive[1] = true;
  _blinkStartMs[0] = now;
  _blinkStartMs[1] = now + 55;
  _renderDirty = true;
}

void EyeManager::handleCommand(const char *cmdIn) {
  if (cmdIn == nullptr) return;

  char cmd[20];
  size_t i = 0;

  // Copy, trim leading whitespace, and lowercase without allocating a String.
  while (*cmdIn == ' ' || *cmdIn == '\t') ++cmdIn;
  while (*cmdIn != '\0' && *cmdIn != ' ' && *cmdIn != '\t' && *cmdIn != '\r' && *cmdIn != '\n') {
    if (i < sizeof(cmd) - 1) {
      char c = *cmdIn++;
      if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
      cmd[i++] = c;
    } else {
      return;
    }
  }
  cmd[i] = '\0';

  if (i == 0) return;

  if (strcmp(cmd, "idle") == 0)           setExpression(EXPR_IDLE);
  else if (strcmp(cmd, "happy") == 0)     setExpression(EXPR_HAPPY);
  else if (strcmp(cmd, "sad") == 0)       setExpression(EXPR_SAD);
  else if (strcmp(cmd, "angry") == 0)     setExpression(EXPR_ANGRY);
  else if (strcmp(cmd, "curious") == 0)   setExpression(EXPR_CURIOUS);
  else if (strcmp(cmd, "sleepy") == 0)    setExpression(EXPR_SLEEPY);
  else if (strcmp(cmd, "surprised") == 0) setExpression(EXPR_SURPRISED);
  else if (strcmp(cmd, "love") == 0)      setExpression(EXPR_LOVE);
  else if (strcmp(cmd, "blink") == 0)     triggerBlink();
  else printHelp();
}

void EyeManager::printHelp() {
  Serial.println(F("Commands: idle, happy, sad, angry, curious, sleepy, surprised, love, blink"));
}

// ---------------------------------------------------------
// Expression poses are intentionally different for each physical eye.
// ---------------------------------------------------------
EyeParams EyeManager::computeExpressionParams(Expression expr, uint8_t eyeIndex) {
  EyeParams p;

  p.w          = (eyeIndex == 0) ? 60.0f : 56.0f;
  p.h          = (eyeIndex == 0) ? 46.0f : 43.0f;
  p.cy         = (eyeIndex == 0) ? 31.0f : 33.0f;
  p.corner     = (eyeIndex == 0) ? 16.0f : 15.0f;
  p.topCut     = 0.0f;
  p.botCut     = 0.0f;
  p.smileCurve = 0.0f;
  p.heartScale = 0.0f;

  switch (expr) {
    case EXPR_IDLE:
      break;

    case EXPR_HAPPY:
      p.w = (eyeIndex == 0) ? 66.0f : 62.0f;
      p.h = (eyeIndex == 0) ? 41.0f : 45.0f;
      p.cy = (eyeIndex == 0) ? 29.0f : 31.0f;
      p.corner = (eyeIndex == 0) ? 17.0f : 15.0f;
      p.smileCurve = (eyeIndex == 0) ? 0.78f : 1.0f;
      break;

    case EXPR_SAD:
      p.w = (eyeIndex == 0) ? 54.0f : 50.0f;
      p.h = (eyeIndex == 0) ? 34.0f : 30.0f;
      p.cy = (eyeIndex == 0) ? 37.0f : 39.0f;
      p.corner = (eyeIndex == 0) ? 11.0f : 9.0f;
      p.topCut = (eyeIndex == 0) ? 4.0f : 7.0f;
      break;

    case EXPR_ANGRY:
      p.w = (eyeIndex == 0) ? 65.0f : 61.0f;
      p.h = (eyeIndex == 0) ? 23.0f : 27.0f;
      p.cy = (eyeIndex == 0) ? 34.0f : 35.0f;
      p.corner = (eyeIndex == 0) ? 4.0f : 6.0f;
      p.topCut = (eyeIndex == 0) ? 7.0f : 3.0f;
      p.botCut = (eyeIndex == 0) ? 1.0f : 3.0f;
      break;

    case EXPR_CURIOUS:
      // The left eye opens taller while the right eye stays closer to neutral.
      p.w = (eyeIndex == 0) ? 48.0f : 58.0f;
      p.h = (eyeIndex == 0) ? 58.0f : 48.0f;
      p.cy = (eyeIndex == 0) ? 27.0f : 31.0f;
      p.corner = (eyeIndex == 0) ? 23.0f : 17.0f;
      break;

    case EXPR_SLEEPY:
      p.w = (eyeIndex == 0) ? 59.0f : 54.0f;
      p.h = (eyeIndex == 0) ? 17.0f : 14.0f;
      p.cy = (eyeIndex == 0) ? 38.0f : 36.0f;
      p.corner = (eyeIndex == 0) ? 7.0f : 5.0f;
      p.topCut = (eyeIndex == 0) ? 3.0f : 5.0f;
      break;

    case EXPR_SURPRISED:
      p.w = (eyeIndex == 0) ? 44.0f : 50.0f;
      p.h = (eyeIndex == 0) ? 59.0f : 54.0f;
      p.cy = (eyeIndex == 0) ? 32.0f : 30.0f;
      p.corner = (eyeIndex == 0) ? 22.0f : 25.0f;
      break;

    case EXPR_LOVE:
      p.heartScale = (eyeIndex == 0) ? 0.88f : 1.0f;
      p.cy = (eyeIndex == 0) ? 31.0f : 29.0f;
      break;

    case EXPR_COUNT:
      break;
  }
  return p;
}

float EyeManager::easeInOutCubic(float t) {
  if (t < 0.0f) t = 0.0f;
  if (t > 1.0f) t = 1.0f;
  return (t < 0.5f) ? (4.0f * t * t * t) : (1.0f - powf(-2.0f * t + 2.0f, 3.0f) / 2.0f);
}

EyeParams EyeManager::getInterpolatedParams(unsigned long now, uint8_t eyeIndex) {
  unsigned long elapsed = now - _transitionStartMs;
  float t = (_transitionDurationMs > 0) ? (float)elapsed / (float)_transitionDurationMs : 1.0f;
  float e = easeInOutCubic(t);

  EyeParams r;
  const EyeParams &from = _fromParams[eyeIndex];
  const EyeParams &to = _toParams[eyeIndex];
  r.w          = from.w          + (to.w          - from.w)          * e;
  r.h          = from.h          + (to.h          - from.h)          * e;
  r.cy         = from.cy         + (to.cy         - from.cy)         * e;
  r.corner     = from.corner     + (to.corner     - from.corner)     * e;
  r.topCut     = from.topCut     + (to.topCut     - from.topCut)     * e;
  r.botCut     = from.botCut     + (to.botCut     - from.botCut)     * e;
  r.smileCurve = from.smileCurve + (to.smileCurve - from.smileCurve) * e;
  r.heartScale = from.heartScale + (to.heartScale - from.heartScale) * e;
  return r;
}

float EyeManager::getBlinkAmount(unsigned long now, uint8_t eyeIndex) {
  if (!_blinkActive[eyeIndex]) return 0.0f;
  if ((long)(now - _blinkStartMs[eyeIndex]) < 0) return 0.0f;
  const unsigned long elapsed = now - _blinkStartMs[eyeIndex];
  if (elapsed >= _blinkDurationMs) {
    _blinkActive[eyeIndex] = false;
    return 0.0f;
  }
  // Close over 80 ms, hold fully closed for 150 ms, then reopen over 130 ms.
  // The closed hold makes the blink visible even when OLED refresh is busy.
  if (elapsed < 80) {
    return easeInOutCubic((float)elapsed / 80.0f);
  }
  if (elapsed < 230) {
    return 1.0f;
  }
  return 1.0f - easeInOutCubic((float)(elapsed - 230) / 130.0f);
}

// ---------------------------------------------------------
// RENDERING
// ---------------------------------------------------------
bool EyeManager::renderFrame(const EyeParams &left, float leftBlink,
                             const EyeParams &right, float rightBlink) {
  renderEye(_leftDisplay, left, leftBlink, true);
  bool leftReady = selectI2cMuxChannel(OLED_LEFT_MUX_CHANNEL);
  if (leftReady) _leftDisplay.display();
  const bool leftMuxReady = deselectI2cMux();

  renderEye(_rightDisplay, right, rightBlink, false);
  bool rightReady = selectI2cMuxChannel(OLED_RIGHT_MUX_CHANNEL);
  if (rightReady) _rightDisplay.display();
  const bool rightMuxReady = deselectI2cMux();
  return leftReady && rightReady && leftMuxReady && rightMuxReady;
}

void EyeManager::renderEye(Adafruit_SSD1306 &display, const EyeParams &p,
                           float blinkAmt, bool leftEye) {
  display.clearDisplay();

  const int16_t cx = leftEye ? 62 : 66;
  int16_t cy = round(p.cy);

  if (p.heartScale > 0.05f) {
    float currentScale = p.heartScale * (1.0f - blinkAmt * 0.9f);
    drawHeart(display, cx, cy, currentScale);
    return;
  }

  float renderH = p.h * (1.0f - blinkAmt * 0.95f);
  if (renderH < 2.0f) renderH = 2.0f;

  int16_t rx = round(cx - p.w / 2.0f);
  int16_t ry = round(cy - renderH / 2.0f);
  int16_t rw = round(p.w);
  int16_t rh = round(renderH);
  int16_t rc = round(p.corner);
  if (rc > rh / 2) rc = rh / 2;

  display.fillRoundRect(rx, ry, rw, rh, rc, SSD1306_WHITE);

  if (p.topCut > 0.5f && blinkAmt < 0.5f) {
    int16_t cutH = round(p.topCut);
    if (leftEye) {
      display.fillTriangle(0, ry - 5, 128, ry - 5 + cutH / 2,
                           128, ry + cutH, SSD1306_BLACK);
    } else {
      display.fillTriangle(0, ry - 5 + cutH / 2, 128, ry - 5,
                           0, ry + cutH, SSD1306_BLACK);
    }
  }

  if (p.botCut > 0.5f && blinkAmt < 0.5f) {
    int16_t cutH = round(p.botCut);
    if (leftEye) {
      display.fillTriangle(0, ry + rh - cutH, 128, ry + rh - cutH / 2,
                           0, ry + rh + 5, SSD1306_BLACK);
    } else {
      display.fillTriangle(0, ry + rh - cutH / 2, 128, ry + rh - cutH,
                           128, ry + rh + 5, SSD1306_BLACK);
    }
  }

  if (p.smileCurve > 0.05f) {
    float smileY = (cy + renderH / 2.0f) - (20.0f * p.smileCurve);
    smileY += (cy - smileY) * blinkAmt;
    const int16_t smileOffset = leftEye ? -3 : 3;
    display.fillRoundRect(cx - 45, round(smileY) + smileOffset,
                          90, 50, 24, SSD1306_BLACK);
  }
}

void EyeManager::drawHeart(Adafruit_SSD1306 &display, int16_t cx,
                           int16_t cy, float scale) {
  int16_t r      = round(14.0f * scale);
  int16_t leftX  = cx - round(12.0f * scale);
  int16_t rightX = cx + round(12.0f * scale);
  int16_t topY   = cy - round(6.0f * scale);
  int16_t botY   = cy + round(22.0f * scale);

  display.fillCircle(leftX, topY, r, SSD1306_WHITE);
  display.fillCircle(rightX, topY, r, SSD1306_WHITE);
  display.fillTriangle(cx - round(25.0f * scale), topY + round(2.0f * scale),
                        cx + round(25.0f * scale), topY + round(2.0f * scale),
                        cx, botY, SSD1306_WHITE);
  display.fillRect(leftX, topY - round(2.0f * scale), rightX - leftX + 1,
                   round(12.0f * scale), SSD1306_WHITE);
}
