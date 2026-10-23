#include "motor_manager.h"

#include <Arduino.h>

namespace {
constexpr uint8_t IN1_PINS[4] = {13, 27, 25, 19};
constexpr uint8_t IN2_PINS[4] = {14, 26, 23, 18};
// M0 already drives the chassis forward; reverse polarity for M1-M3.
constexpr bool MOTOR_REVERSED[4] = {false, true, true, true};
// Physical motor M0..M3 correspond to encoder IDs 4, 2, 3, 1.
constexpr uint8_t MOTOR_ENCODER_INDEX[4] = {3, 1, 2, 0};
constexpr uint8_t ENCODER_PINS[4] = {15, 35, 39, 33};
constexpr unsigned long CONTROL_INTERVAL_MS = 250;
constexpr float PID_KP = 0.45f;
constexpr float PID_KI = 0.12f;
constexpr float PID_KD = 0.005f;
constexpr float MAX_CORRECTION_FRACTION = 0.35f;
constexpr float MIN_CONTROL_RATE = 0.5f;
}

volatile uint32_t MotorManager::encoderCounts[4] = {0, 0, 0, 0};

bool MotorManager::begin() {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        pinMode(IN1_PINS[motor], OUTPUT);
        pinMode(IN2_PINS[motor], OUTPUT);
        digitalWrite(IN1_PINS[motor], LOW);
        digitalWrite(IN2_PINS[motor], LOW);
        pinMode(ENCODER_PINS[motor], INPUT);
    }
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[0]), encoder0ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[1]), encoder1ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[2]), encoder2ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[3]), encoder3ISR, RISING);

    uint32_t counts[MOTOR_COUNT];
    noInterrupts();
    for (uint8_t encoder = 0; encoder < MOTOR_COUNT; ++encoder) {
        counts[encoder] = encoderCounts[encoder];
    }
    interrupts();
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        previousEncoderCounts[motor] = counts[MOTOR_ENCODER_INDEX[motor]];
    }

    stop();
    lastControlMs = millis();
    initialized = true;
    return true;
}

void MotorManager::setMotor(uint8_t motor, int16_t speed) {
    if (motor >= MOTOR_COUNT) return;
    if (speed > static_cast<int16_t>(MAX_SPEED)) speed = MAX_SPEED;
    else if (speed < -static_cast<int16_t>(MAX_SPEED)) speed = -MAX_SPEED;
    if (requestedSpeed[motor] == speed) return;

    requestedSpeed[motor] = speed;
    integralError[motor] = 0.0f;
    previousError[motor] = 0.0f;
    measuredCountsPerSecond[motor] = 0.0f;
    noInterrupts();
    previousEncoderCounts[motor] = encoderCounts[MOTOR_ENCODER_INDEX[motor]];
    interrupts();
    writeMotor(motor, speed);
}

void MotorManager::setAll(int16_t speed) {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) setMotor(motor, speed);
}

void MotorManager::stop() {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        requestedSpeed[motor] = 0;
        integralError[motor] = 0.0f;
        previousError[motor] = 0.0f;
        measuredCountsPerSecond[motor] = 0.0f;
        writeMotor(motor, 0);
    }
}

void MotorManager::update() {
    if (!initialized) return;
    const unsigned long now = millis();
    const unsigned long elapsedMs = now - lastControlMs;
    if (elapsedMs < CONTROL_INTERVAL_MS) return;
    lastControlMs = now;
    const float dt = elapsedMs / 1000.0f;

    uint32_t counts[MOTOR_COUNT];
    noInterrupts();
    for (uint8_t encoder = 0; encoder < MOTOR_COUNT; ++encoder) {
        counts[encoder] = encoderCounts[encoder];
    }
    interrupts();

    float rateSum = 0.0f;
    uint8_t activeCount = 0;
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        const uint8_t encoder = MOTOR_ENCODER_INDEX[motor];
        const uint32_t delta = counts[encoder] - previousEncoderCounts[motor];
        previousEncoderCounts[motor] = counts[encoder];

        if (requestedSpeed[motor] == 0) {
            measuredCountsPerSecond[motor] = 0.0f;
            integralError[motor] = 0.0f;
            previousError[motor] = 0.0f;
            continue;
        }

        const float rawRate = (delta * 1000.0f) / elapsedMs;
        measuredCountsPerSecond[motor] =
            0.5f * measuredCountsPerSecond[motor] + 0.5f * rawRate;
        rateSum += measuredCountsPerSecond[motor];
        ++activeCount;
    }

    // One motor alone has no peer reference; keep its requested PWM unchanged.
    if (activeCount < 2) return;
    const float targetRate = rateSum / activeCount;
    if (targetRate < MIN_CONTROL_RATE) return;

    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        const int16_t requested = requestedSpeed[motor];
        if (requested == 0) continue;

        float error = (targetRate - measuredCountsPerSecond[motor]) / targetRate;
        if (error > 1.0f) error = 1.0f;
        else if (error < -1.0f) error = -1.0f;

        float candidateIntegral = integralError[motor] + error * dt;
        if (candidateIntegral > 1.5f) candidateIntegral = 1.5f;
        else if (candidateIntegral < -1.5f) candidateIntegral = -1.5f;
        const float derivative = (error - previousError[motor]) / dt;
        float correction = PID_KP * error +
                           PID_KI * candidateIntegral +
                           PID_KD * derivative;

        // Anti-windup: do not integrate farther into the correction limit.
        if (!((correction > MAX_CORRECTION_FRACTION && error > 0.0f) ||
              (correction < -MAX_CORRECTION_FRACTION && error < 0.0f))) {
            integralError[motor] = candidateIntegral;
        } else {
            correction = PID_KP * error +
                         PID_KI * integralError[motor] +
                         PID_KD * derivative;
        }
        previousError[motor] = error;
        if (correction > MAX_CORRECTION_FRACTION) correction = MAX_CORRECTION_FRACTION;
        else if (correction < -MAX_CORRECTION_FRACTION) correction = -MAX_CORRECTION_FRACTION;

        const float baseDuty = requested < 0 ? -requested : requested;
        float correctedDuty = baseDuty * (1.0f + correction);
        if (correctedDuty > MAX_SPEED) correctedDuty = MAX_SPEED;
        else if (correctedDuty < 0.0f) correctedDuty = 0.0f;
        const int16_t duty = static_cast<int16_t>(correctedDuty + 0.5f);
        writeMotor(motor, requested < 0 ? -duty : duty);
    }
}

bool MotorManager::isReady() const { return initialized; }

uint32_t MotorManager::encoderCount(uint8_t encoderId) const {
    return encoderId < MOTOR_COUNT ? encoderCounts[encoderId] : 0;
}

void MotorManager::writeMotor(uint8_t motor, int16_t speed) {
    if (speed == 0) {
        analogWrite(IN1_PINS[motor], 0);
        analogWrite(IN2_PINS[motor], 0);
        return;
    }
    const uint8_t duty = static_cast<uint8_t>(speed < 0 ? -speed : speed);
    analogWrite(IN1_PINS[motor], 0);
    analogWrite(IN2_PINS[motor], 0);
    const bool driveForward = (speed > 0) != MOTOR_REVERSED[motor];
    if (driveForward) analogWrite(IN1_PINS[motor], duty);
    else analogWrite(IN2_PINS[motor], duty);
}

void IRAM_ATTR MotorManager::encoder0ISR() { ++encoderCounts[0]; }
void IRAM_ATTR MotorManager::encoder1ISR() { ++encoderCounts[1]; }
void IRAM_ATTR MotorManager::encoder2ISR() { ++encoderCounts[2]; }
void IRAM_ATTR MotorManager::encoder3ISR() { ++encoderCounts[3]; }
