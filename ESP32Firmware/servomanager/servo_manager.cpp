#include "servo_manager.h"
#include <ESP32Servo.h>
#include <math.h>

// ============================================================
// PIN CONFIGURATION
// ============================================================

static constexpr int PAN_PIN  = 5;
static constexpr int TILT_PIN = 15;

// ============================================================
// SERVO LIMITS
// ============================================================

static constexpr float PAN_MIN  = 45.0f;
static constexpr float PAN_MAX  = 135.0f;

static constexpr float TILT_MIN = 30.0f;
static constexpr float TILT_MAX = 135.0f;

static constexpr float CENTER_ANGLE = 90.0f;

// ============================================================
// PWM CONFIGURATION
// ============================================================

static constexpr int SERVO_MIN_US = 500;
static constexpr int SERVO_MAX_US = 2400;

static constexpr int SERVO_FREQUENCY = 50;

// ============================================================
// UPDATE RATE
// ============================================================

static constexpr unsigned long UPDATE_INTERVAL_MS = 20;

// ============================================================
// TRACKING CONFIGURATION
// ============================================================

static constexpr float TRACK_GAIN = 0.15f;
static constexpr float TRACK_MAX_STEP = 3.0f;
static constexpr float TRACK_MIN_STEP = 0.15f;

// ============================================================
// INTERNAL STATE
// ============================================================

enum class MotionMode {
    IDLE,
    MOVE,
    TRACK,
    STOP
};

struct ServoAxis {
    float currentAngle;
    float startAngle;
    float targetAngle;

    unsigned long startTime;
    unsigned long duration;

    bool moving;
};

static Servo panServo;
static Servo tiltServo;

static ServoAxis pan = {
    CENTER_ANGLE,
    CENTER_ANGLE,
    CENTER_ANGLE,
    0,
    0,
    false
};

static ServoAxis tilt = {
    CENTER_ANGLE,
    CENTER_ANGLE,
    CENTER_ANGLE,
    0,
    0,
    false
};

static MotionMode mode = MotionMode::IDLE;

static float trackingPanTarget  = CENTER_ANGLE;
static float trackingTiltTarget = CENTER_ANGLE;

static unsigned long lastUpdate = 0;

// ============================================================
// HELPER FUNCTIONS
// ============================================================

static float limitPan(float angle)
{
    return constrain(angle, PAN_MIN, PAN_MAX);
}

static float limitTilt(float angle)
{
    return constrain(angle, TILT_MIN, TILT_MAX);
}

static float easeInOutCubic(float t)
{
    if (t < 0.5f) {
        return 4.0f * t * t * t;
    }

    float f = (2.0f * t) - 2.0f;

    return 0.5f * f * f * f + 1.0f;
}

// Convert 0-180 degree position into servo pulse width.
static int angleToMicroseconds(float angle)
{
    angle = constrain(angle, 0.0f, 180.0f);

    float ratio = angle / 180.0f;

    return SERVO_MIN_US +
           (int)round(
               ratio *
               (SERVO_MAX_US - SERVO_MIN_US)
           );
}

static void writePan(float angle)
{
    panServo.writeMicroseconds(
        angleToMicroseconds(angle)
    );
}

static void writeTilt(float angle)
{
    tiltServo.writeMicroseconds(
        angleToMicroseconds(angle)
    );
}

// ============================================================
// NORMAL MOVE
// ============================================================

static void startMove(
    ServoAxis &axis,
    float target,
    unsigned long duration
)
{
    axis.startAngle = axis.currentAngle;
    axis.targetAngle = target;

    axis.startTime = millis();
    axis.duration = duration;

    axis.moving = true;
}

static void updateMove(
    ServoAxis &axis,
    bool isPan
)
{
    if (!axis.moving) {
        return;
    }

    unsigned long elapsed =
        millis() - axis.startTime;

    if (elapsed >= axis.duration) {

        axis.currentAngle =
            axis.targetAngle;

        axis.moving = false;

    } else {

        float t =
            (float)elapsed /
            (float)axis.duration;

        float easedT =
            easeInOutCubic(t);

        axis.currentAngle =
            axis.startAngle +
            (
                axis.targetAngle -
                axis.startAngle
            ) * easedT;
    }

    if (isPan) {
        writePan(axis.currentAngle);
    } else {
        writeTilt(axis.currentAngle);
    }
}

// ============================================================
// TRACKING
// ============================================================

static void updateTracking(
    ServoAxis &axis,
    float target,
    bool isPan
)
{
    float difference =
        target - axis.currentAngle;

    float absoluteDifference =
        fabs(difference);

    if (absoluteDifference < 0.01f) {
        axis.currentAngle = target;
    } else {

        float step =
            absoluteDifference * TRACK_GAIN;

        step = constrain(
            step,
            TRACK_MIN_STEP,
            TRACK_MAX_STEP
        );

        if (difference > 0.0f) {
            axis.currentAngle += step;
        } else {
            axis.currentAngle -= step;
        }
    }

    if (isPan) {
        axis.currentAngle =
            limitPan(axis.currentAngle);

        writePan(axis.currentAngle);

    } else {
        axis.currentAngle =
            limitTilt(axis.currentAngle);

        writeTilt(axis.currentAngle);
    }
}

// ============================================================
// PUBLIC API
// ============================================================

bool ServoManager::begin()
{
    // Explicit timer allocation is required
    // for our verified ESP32Servo setup.

    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);

    panServo.setPeriodHertz(
        SERVO_FREQUENCY
    );

    tiltServo.setPeriodHertz(
        SERVO_FREQUENCY
    );

    panServo.attach(
        PAN_PIN,
        SERVO_MIN_US,
        SERVO_MAX_US
    );

    tiltServo.attach(
        TILT_PIN,
        SERVO_MIN_US,
        SERVO_MAX_US
    );

    if (!panServo.attached() ||
        !tiltServo.attached()) {

        return false;
    }

    pan.currentAngle = CENTER_ANGLE;
    pan.startAngle = CENTER_ANGLE;
    pan.targetAngle = CENTER_ANGLE;

    tilt.currentAngle = CENTER_ANGLE;
    tilt.startAngle = CENTER_ANGLE;
    tilt.targetAngle = CENTER_ANGLE;

    trackingPanTarget = CENTER_ANGLE;
    trackingTiltTarget = CENTER_ANGLE;

    writePan(CENTER_ANGLE);
    writeTilt(CENTER_ANGLE);

    mode = MotionMode::IDLE;

    lastUpdate = millis();

    return true;
}

void ServoManager::update()
{
    unsigned long now = millis();

    if (now - lastUpdate <
        UPDATE_INTERVAL_MS) {

        return;
    }

    lastUpdate = now;

    if (mode == MotionMode::MOVE) {

        updateMove(pan, true);
        updateMove(tilt, false);

        if (!pan.moving &&
            !tilt.moving) {

            mode = MotionMode::IDLE;
        }

    } else if (mode == MotionMode::TRACK) {

        updateTracking(
            pan,
            trackingPanTarget,
            true
        );

        updateTracking(
            tilt,
            trackingTiltTarget,
            false
        );
    }
}

void ServoManager::moveTo(
    float panAngle,
    float tiltAngle,
    unsigned long durationMs
)
{
    panAngle = limitPan(panAngle);
    tiltAngle = limitTilt(tiltAngle);

    if (durationMs < 20) {
        durationMs = 20;
    }

    startMove(
        pan,
        panAngle,
        durationMs
    );

    startMove(
        tilt,
        tiltAngle,
        durationMs
    );

    mode = MotionMode::MOVE;
}

void ServoManager::track(
    float panAngle,
    float tiltAngle
)
{
    trackingPanTarget =
        limitPan(panAngle);

    trackingTiltTarget =
        limitTilt(tiltAngle);

    mode = MotionMode::TRACK;
}

void ServoManager::center()
{
    moveTo(
        CENTER_ANGLE,
        CENTER_ANGLE,
        800
    );
}

void ServoManager::stop()
{
    pan.moving = false;
    tilt.moving = false;

    trackingPanTarget =
        pan.currentAngle;

    trackingTiltTarget =
        tilt.currentAngle;

    mode = MotionMode::STOP;
}

bool ServoManager::isMoving() const
{
    return pan.moving ||
           tilt.moving;
}

float ServoManager::getPanAngle() const
{
    return pan.currentAngle;
}

float ServoManager::getTiltAngle() const
{
    return tilt.currentAngle;
}