#include "eye_manager.h"
#include <math.h>

EyeManager::EyeManager()
: _display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET_PIN),
  _transitionStartMs(0),
  _transitionDurationMs(1),
  _currentTarget(EXPR_IDLE),
  _blinkActive(false),
  _blinkStartMs(0),
  _blinkDurationMs(200) {

  _currentParams = computeExpressionParams(EXPR_IDLE);
  _fromParams    = _currentParams;
  _toParams      = _currentParams;
}

void EyeManager::begin() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  Wire.setClock(400000);

  _display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  _display.clearDisplay();
  _display.display();

  renderFrame(_currentParams, 0.0f);
}

void EyeManager::update() {
  static unsigned long lastFrameMs = 0;
  unsigned long now = millis();

  const bool transitionActive = (now - _transitionStartMs) < _transitionDurationMs;
  const bool blinkActive = _blinkActive;

  // Once the expression and blink are both settled, the OLED already contains
  // the correct frame. Do not repeatedly retransmit the same framebuffer.
  if (!transitionActive && !blinkActive) return;

  // ~35 FPS cap during active animation, leaving the shared I2C bus available
  // for the ToF sensors between OLED frame transfers.
  if (now - lastFrameMs < 28) return;
  lastFrameMs = now;

  EyeParams p = getInterpolatedParams(now);
  float blinkAmt = getBlinkAmount(now);

  renderFrame(p, blinkAmt);

  // A blink can finish during getBlinkAmount(). The final open frame is rendered
  // above; subsequent update() calls return immediately once the transition is done.
}

void EyeManager::setExpression(Expression expr) {
  unsigned long now = millis();
  _fromParams = getInterpolatedParams(now);
  _toParams   = computeExpressionParams(expr);
  _transitionStartMs = now;
  _transitionDurationMs = 250;
  _currentTarget = expr;
}

void EyeManager::triggerBlink() {
  if (_blinkActive) return;
  _blinkActive = true;
  _blinkStartMs = millis();
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

  if (strcmp(cmd, "idle") == 0)          setExpression(EXPR_IDLE);
  else if (strcmp(cmd, "happy") == 0)    setExpression(EXPR_HAPPY);
  else if (strcmp(cmd, "sad") == 0)      setExpression(EXPR_SAD);
  else if (strcmp(cmd, "angry") == 0)    setExpression(EXPR_ANGRY);
  else if (strcmp(cmd, "curious") == 0)  setExpression(EXPR_CURIOUS);
  else if (strcmp(cmd, "sleepy") == 0)   setExpression(EXPR_SLEEPY);
  else if (strcmp(cmd, "surprised") == 0) setExpression(EXPR_SURPRISED);
  else if (strcmp(cmd, "love") == 0)     setExpression(EXPR_LOVE);
  else if (strcmp(cmd, "blink") == 0)    triggerBlink();
  else printHelp();
}

void EyeManager::printHelp() {
  Serial.println(F("Commands: idle, happy, sad, angry, curious, sleepy, surprised, love, blink"));
}

// ---------------------------------------------------------
// SYMMETRICAL EXPRESSION DEFINITIONS
// ---------------------------------------------------------
EyeParams EyeManager::computeExpressionParams(Expression expr) {
  EyeParams p;

  p.w          = 60.0f;
  p.h          = 46.0f;
  p.cy         = 32.0f;
  p.corner     = 16.0f;
  p.topCut     = 0.0f;
  p.botCut     = 0.0f;
  p.smileCurve = 0.0f;
  p.heartScale = 0.0f;

  switch (expr) {
    case EXPR_IDLE:
      break;

    case EXPR_HAPPY:
      p.w = 64.0f;
      p.h = 44.0f;
      p.cy = 30.0f;
      p.smileCurve = 1.0f;
      break;

    case EXPR_SAD:
      p.w = 52.0f;
      p.h = 32.0f;
      p.cy = 38.0f;
      p.corner = 10.0f;
      p.topCut = 6.0f;
      break;

    case EXPR_ANGRY:
      p.w = 64.0f;
      p.h = 24.0f;
      p.cy = 34.0f;
      p.corner = 4.0f;
      p.topCut = 4.0f;
      p.botCut = 2.0f;
      break;

    case EXPR_CURIOUS:
      p.w = 52.0f;
      p.h = 54.0f;
      p.cy = 27.0f;
      p.corner = 20.0f;
      break;

    case EXPR_SLEEPY:
      p.w = 58.0f;
      p.h = 16.0f;
      p.cy = 38.0f;
      p.corner = 6.0f;
      p.topCut = 4.0f;
      break;

    case EXPR_SURPRISED:
      p.w = 46.0f;
      p.h = 58.0f;
      p.cy = 32.0f;
      p.corner = 23.0f;
      break;

    case EXPR_LOVE:
      p.heartScale = 1.0f;
      p.cy = 30.0f;
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

EyeParams EyeManager::getInterpolatedParams(unsigned long now) {
  unsigned long elapsed = now - _transitionStartMs;
  float t = (_transitionDurationMs > 0) ? (float)elapsed / (float)_transitionDurationMs : 1.0f;
  float e = easeInOutCubic(t);

  EyeParams r;
  r.w          = _fromParams.w          + (_toParams.w          - _fromParams.w)          * e;
  r.h          = _fromParams.h          + (_toParams.h          - _fromParams.h)          * e;
  r.cy         = _fromParams.cy         + (_toParams.cy         - _fromParams.cy)         * e;
  r.corner     = _fromParams.corner     + (_toParams.corner     - _fromParams.corner)     * e;
  r.topCut     = _fromParams.topCut     + (_toParams.topCut     - _fromParams.topCut)     * e;
  r.botCut     = _fromParams.botCut     + (_toParams.botCut     - _fromParams.botCut)     * e;
  r.smileCurve = _fromParams.smileCurve + (_toParams.smileCurve - _fromParams.smileCurve) * e;
  r.heartScale = _fromParams.heartScale + (_toParams.heartScale - _fromParams.heartScale) * e;
  return r;
}

float EyeManager::getBlinkAmount(unsigned long now) {
  if (!_blinkActive) return 0.0f;
  unsigned long elapsed = now - _blinkStartMs;
  if (elapsed >= _blinkDurationMs) {
    _blinkActive = false;
    return 0.0f;
  }
  float t = (float)elapsed / (float)_blinkDurationMs;
  return (t < 0.5f) ? easeInOutCubic(t / 0.5f) : 1.0f - easeInOutCubic((t - 0.5f) / 0.5f);
}

// ---------------------------------------------------------
// RENDERING
// ---------------------------------------------------------
void EyeManager::renderFrame(const EyeParams &p, float blinkAmt) {
  _display.clearDisplay();

  const int16_t cx = 64;
  int16_t cy = round(p.cy);

  if (p.heartScale > 0.05f) {
    float currentScale = p.heartScale * (1.0f - blinkAmt * 0.9f);
    drawHeart(cx, cy, currentScale);
    _display.display();
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

  _display.fillRoundRect(rx, ry, rw, rh, rc, SSD1306_WHITE);

  if (p.topCut > 0.5f && blinkAmt < 0.5f) {
    int16_t cutH = round(p.topCut);
    _display.fillRect(0, ry - 5, 128, cutH + 5, SSD1306_BLACK);
  }

  if (p.botCut > 0.5f && blinkAmt < 0.5f) {
    int16_t cutH = round(p.botCut);
    _display.fillRect(0, ry + rh - cutH, 128, cutH + 5, SSD1306_BLACK);
  }

  if (p.smileCurve > 0.05f) {
    float smileY = (cy + renderH / 2.0f) - (20.0f * p.smileCurve);
    smileY += (cy - smileY) * blinkAmt;
    _display.fillRoundRect(cx - 45, round(smileY), 90, 50, 24, SSD1306_BLACK);
  }

  _display.display();
}

void EyeManager::drawHeart(int16_t cx, int16_t cy, float scale) {
  int16_t r      = round(14.0f * scale);
  int16_t leftX  = cx - round(12.0f * scale);
  int16_t rightX = cx + round(12.0f * scale);
  int16_t topY   = cy - round(6.0f * scale);
  int16_t botY   = cy + round(22.0f * scale);

  _display.fillCircle(leftX, topY, r, SSD1306_WHITE);
  _display.fillCircle(rightX, topY, r, SSD1306_WHITE);
  _display.fillTriangle(cx - round(25.0f * scale), topY + round(2.0f * scale),
                        cx + round(25.0f * scale), topY + round(2.0f * scale),
                        cx, botY, SSD1306_WHITE);
  _display.fillRect(leftX, topY - round(2.0f * scale), rightX - leftX + 1, round(12.0f * scale), SSD1306_WHITE);
}