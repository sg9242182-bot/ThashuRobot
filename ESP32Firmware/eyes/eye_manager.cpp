#include "eye_manager.h"

#include <Wire.h>
#include <math.h>

EyeManager::EyeManager()
    : leftDisplay(WIDTH, HEIGHT, &Wire, -1),
      rightDisplay(WIDTH, HEIGHT, &Wire, -1) {}

bool EyeManager::begin(uint8_t leftAddress, uint8_t rightAddress) {
    Wire.begin(SDA_PIN, SCL_PIN);
    if (!leftDisplay.begin(SSD1306_SWITCHCAPVCC, leftAddress)) return false;
    if (!rightDisplay.begin(SSD1306_SWITCHCAPVCC, rightAddress)) return false;

    ready = true;
    currentExpression = IDLE;
    targetExpression = IDLE;
    blinkReturnExpression = IDLE;
    currentPose = poseFor(IDLE);
    startPose = currentPose;
    targetPose = currentPose;
    transitioning = false;
    blinkActive = false;
    blinkFrame = 0;
    lastFrame = millis();
    render();
    return true;
}

void EyeManager::update() {
    if (!ready) return;
    const unsigned long now = millis();
    if (now - lastFrame < FRAME_MS) return;
    lastFrame = now;

    if (blinkActive) {
        ++blinkFrame;
        if (blinkFrame >= 8) {
            blinkActive = false;
            currentExpression = blinkReturnExpression;
            targetExpression = blinkReturnExpression;
            currentPose = poseFor(currentExpression);
            startPose = currentPose;
            targetPose = currentPose;
            transitioning = false;
            blinkFrame = 0;
        }
        render();
        return;
    }

    if (!transitioning) return;
    float t = static_cast<float>(now - transitionStart) / static_cast<float>(TRANSITION_MS);
    if (t >= 1.0f) t = 1.0f;
    currentPose = interpolate(startPose, targetPose, easeInOut(t));
    if (t >= 1.0f) {
        currentExpression = targetExpression;
        currentPose = targetPose;
        transitioning = false;
    }
    render();
}

void EyeManager::setExpression(Expression newExpression) {
    if (!ready || newExpression >= EXPRESSION_COUNT) return;

    if (newExpression == BLINK) {
        blinkReturnExpression = transitioning ? targetExpression : currentExpression;
        blinkActive = true;
        blinkFrame = 0;
        transitioning = false;
        render();
        return;
    }

    startPose = currentPose;
    targetPose = poseFor(newExpression);
    targetExpression = newExpression;
    transitionStart = millis();
    transitioning = true;
}

EyeManager::Expression EyeManager::getExpression() const { return targetExpression; }
bool EyeManager::isReady() const { return ready; }

EyeManager::Pose EyeManager::poseFor(Expression e) const {
    Pose p{1, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0};
    switch (e) {
        case IDLE: break;
        case HAPPY: p.openness=0.18f; p.height=0.78f; p.upperLid=0.10f; break;
        case SAD: p.openness=0.72f; p.height=0.92f; p.pupilY=0.18f; p.upperLid=0.20f; p.lowerLid=0.10f; p.brow=0.85f; p.browTilt=-0.75f; break;
        case ANGRY: p.openness=0.68f; p.height=0.86f; p.pupilY=0.10f; p.upperLid=0.30f; p.brow=1.0f; p.browTilt=1.0f; break;
        case CURIOUS: p.openness=0.98f; p.width=1.08f; p.height=1.08f; p.pupilX=0.22f; p.pupilY=-0.04f; p.brow=0.55f; p.browTilt=-0.55f; break;
        case SLEEPY: p.openness=0.32f; p.height=0.76f; p.pupilY=0.18f; p.upperLid=0.65f; break;
        case WINK: p.openness=0.96f; p.width=1.02f; break;
        case SURPRISED: p.openness=1.12f; p.width=0.90f; p.height=1.16f; p.pupilWidth=0.78f; p.pupilHeight=1.12f; break;
        case CONFUSED: p.openness=0.78f; p.height=0.90f; p.pupilX=-0.18f; p.pupilY=0.08f; p.brow=0.75f; p.browTilt=-1.0f; break;
        case LOVE: p.openness=0.95f; break;
        default: break;
    }
    return p;
}

EyeManager::Pose EyeManager::interpolate(const Pose& a, const Pose& b, float t) {
    Pose p{};
    const float* A = reinterpret_cast<const float*>(&a);
    const float* B = reinterpret_cast<const float*>(&b);
    float* P = reinterpret_cast<float*>(&p);
    for (uint8_t i=0; i<11; ++i) P[i] = A[i] + (B[i]-A[i])*t;
    return p;
}

float EyeManager::easeInOut(float t) {
    return t < 0.5f ? 2.0f*t*t : 1.0f - powf(-2.0f*t+2.0f, 2.0f)/2.0f;
}

void EyeManager::render() {
    leftDisplay.clearDisplay();
    rightDisplay.clearDisplay();
    if (blinkActive) {
        renderBlink(leftDisplay, true);
        renderBlink(rightDisplay, false);
    } else {
        renderEye(leftDisplay, true, currentPose);
        renderEye(rightDisplay, false, currentPose);
    }
    leftDisplay.display();
    rightDisplay.display();
}

void EyeManager::renderEye(Adafruit_SSD1306& display, bool leftEye, const Pose& pose) {
    if (targetExpression == WINK && !transitioning) {
        if (leftEye) {
            drawBaseEye(display, pose);
            drawPupil(display, pose);
        } else {
            Pose closed = pose;
            closed.openness = 0.10f;
            drawBaseEye(display, closed);
        }
        return;
    }
    if (targetExpression == LOVE && !transitioning) {
        drawLoveMark(display);
        return;
    }
    drawBaseEye(display, pose);
    drawPupil(display, pose);
    drawLids(display, pose, leftEye);
    drawBrow(display, pose, leftEye);
}

void EyeManager::renderBlink(Adafruit_SSD1306& display, bool leftEye) {
    (void)leftEye;
    Pose p = currentPose;
    if (blinkFrame <= 1) {
        p.openness = 1.0f - 0.35f * blinkFrame;
        drawBaseEye(display, p);
        drawPupil(display, p);
    } else if (blinkFrame <= 5) {
        drawThickLine(display, 30, 34, 98, 34, 6);
    } else {
        p.openness = 0.25f + 0.35f * (blinkFrame - 5);
        drawBaseEye(display, p);
        drawPupil(display, p);
    }
}

void EyeManager::drawBaseEye(Adafruit_SSD1306& display, const Pose& pose) {
    fillOrganicEye(display, 64, 34,
                   static_cast<int16_t>(26.0f*pose.width),
                   static_cast<int16_t>(25.0f*pose.height), pose.openness);
}

void EyeManager::drawPupil(Adafruit_SSD1306& display, const Pose& pose) {
    const int16_t cx = 64 + static_cast<int16_t>(pose.pupilX*13.0f);
    const int16_t cy = 34 + static_cast<int16_t>(pose.pupilY*12.0f);
    const int16_t w = max<int16_t>(5, static_cast<int16_t>(9.0f*pose.pupilWidth));
    const int16_t h = max<int16_t>(7, static_cast<int16_t>(15.0f*pose.pupilHeight));
    display.fillRoundRect(cx-w/2, cy-h/2, w, h, min(w/2,h/2), SSD1306_BLACK);
    display.fillRect(cx-2, cy-h/2+3, 3, 3, SSD1306_WHITE);
}

void EyeManager::drawLids(Adafruit_SSD1306& display, const Pose& pose, bool leftEye) {
    if (pose.upperLid > 0.01f) eraseLid(display,64,34,static_cast<int16_t>(28*pose.width),static_cast<int16_t>(24*pose.height),pose.upperLid,true,leftEye);
    if (pose.lowerLid > 0.01f) eraseLid(display,64,34,static_cast<int16_t>(28*pose.width),static_cast<int16_t>(24*pose.height),pose.lowerLid,false,leftEye);
}

void EyeManager::drawBrow(Adafruit_SSD1306& display, const Pose& pose, bool leftEye) {
    if (pose.brow < 0.05f) return;
    const int16_t y = 10 - static_cast<int16_t>(pose.brow*3.0f);
    const int16_t tilt = static_cast<int16_t>(pose.browTilt*9.0f);
    if (leftEye) drawThickLine(display,31,y+tilt,57,y-tilt,4);
    else drawThickLine(display,97,y+tilt,71,y-tilt,4);
}

void EyeManager::drawLoveMark(Adafruit_SSD1306& display) {
    display.fillCircle(54,29,9,SSD1306_WHITE);
    display.fillCircle(74,29,9,SSD1306_WHITE);
    display.fillTriangle(45,34,83,34,64,54,SSD1306_WHITE);
}

void EyeManager::fillOrganicEye(Adafruit_SSD1306& display, int16_t cx, int16_t cy,
                                int16_t halfWidth, int16_t halfHeight, float openness) {
    openness = constrain(openness,0.05f,1.25f);
    const float openHeight = halfHeight*openness;
    const int16_t top=static_cast<int16_t>(cy-openHeight);
    const int16_t bottom=static_cast<int16_t>(cy+openHeight);
    for (int16_t y=top; y<=bottom; ++y) {
        const float ny=static_cast<float>(y-cy)/max(openHeight,1.0f);
        const float shape=sqrtf(max(0.0f,1.0f-ny*ny));
        const float taper=0.88f+0.12f*shape;
        const int16_t w=static_cast<int16_t>(halfWidth*shape*taper);
        if (w>0) display.drawFastHLine(cx-w,y,w*2+1,SSD1306_WHITE);
    }
}

void EyeManager::eraseLid(Adafruit_SSD1306& display,int16_t cx,int16_t cy,int16_t halfWidth,
                           int16_t halfHeight,float amount,bool upper,bool leftEye) {
    amount=constrain(amount,0.0f,1.0f);
    const int16_t offset=static_cast<int16_t>(halfHeight*(0.05f+amount*0.55f));
    const int16_t centerY=upper?cy-offset:cy+offset;
    const int16_t eraseH=static_cast<int16_t>(halfHeight*(0.35f+amount*0.55f));
    for (int16_t y=centerY-eraseH;y<=centerY+eraseH;++y) {
        const float ny=static_cast<float>(y-centerY)/max(static_cast<float>(eraseH),1.0f);
        const float shape=sqrtf(max(0.0f,1.0f-ny*ny));
        const int16_t w=static_cast<int16_t>(halfWidth*shape);
        const int16_t shift=leftEye?1:-1;
        display.drawFastHLine(cx-w+shift,y,w*2+1,SSD1306_BLACK);
    }
}

void EyeManager::drawThickLine(Adafruit_SSD1306& display,int16_t x0,int16_t y0,int16_t x1,int16_t y1,uint8_t thickness) {
    const int16_t half=thickness/2;
    for (int16_t i=-half;i<=half;++i) display.drawLine(x0,y0+i,x1,y1+i,SSD1306_WHITE);
}
