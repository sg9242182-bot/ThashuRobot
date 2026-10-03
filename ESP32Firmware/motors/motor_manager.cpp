#include "motor_manager.h"

#include <Arduino.h>

namespace {
// Motor order follows the proposed pin allocation: driver 1 channels 1 and 2,
// then driver 2 channels 1 and 2. Physical wheel placement must be confirmed.
constexpr uint8_t IN1_PINS[4] = {13, 27, 25, 19};
constexpr uint8_t IN2_PINS[4] = {14, 26, 23, 18};
constexpr uint8_t SLEEP_PIN = 32;
constexpr uint8_t FAULT_PIN = 34;
constexpr uint8_t ENCODER_PINS[4] = {33, 35, 39, 15};
constexpr ToFManager::SensorId FRONT_SENSORS[ToFManager::SENSOR_COUNT] = {
    ToFManager::FRONT_LEFT,
    ToFManager::FRONT_CENTER,
    ToFManager::FRONT_RIGHT,
};
}

volatile uint32_t MotorManager::encoderCounts[4] = {0, 0, 0, 0};

bool MotorManager::begin(ToFManager& frontTof) {
    // Both modules share nSLEEP; hold every bridge asleep during setup.
    pinMode(SLEEP_PIN, OUTPUT);
    digitalWrite(SLEEP_PIN, LOW);

    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        pinMode(IN1_PINS[motor], OUTPUT);
        pinMode(IN2_PINS[motor], OUTPUT);
        digitalWrite(IN1_PINS[motor], LOW);
        digitalWrite(IN2_PINS[motor], LOW);
    }
    // GPIO34 has no internal pull-up. The shared open-drain fault net needs
    // a verified module pull-up or an external pull-up to 3.3 V.
    pinMode(FAULT_PIN, INPUT);

    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        pinMode(ENCODER_PINS[motor], INPUT);
    }
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[0]), encoder0ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[1]), encoder1ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[2]), encoder2ISR, RISING);
    attachInterrupt(digitalPinToInterrupt(ENCODER_PINS[3]), encoder3ISR, RISING);

    tof = &frontTof;
    if (!tof->begin()) {
        stop();
        return false;
    }

    lastPiMessageMs = millis();
    watchdogExpired = true;
    stop();
    return true;
}

void MotorManager::update() {
    if (tof != nullptr) {
        tof->update();
    }

    if (millis() - lastPiMessageMs >= PI_WATCHDOG_MS) {
        watchdogExpired = true;
    }

    if (watchdogExpired || driverFaulted()) {
        stop();
        return;
    }

    // Re-check while moving so a newly detected obstacle stops the drivetrain.
    if (!frontMotionAllowed()) {
        for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
            if (currentSpeed[motor] > 0) {
                stop();
                return;
            }
        }
    }
}

void MotorManager::setMotor(uint8_t motor, int16_t speed) {
    if (motor >= MOTOR_COUNT) {
        return;
    }
    if (speed > static_cast<int16_t>(MAX_SPEED)) {
        speed = MAX_SPEED;
    } else if (speed < -static_cast<int16_t>(MAX_SPEED)) {
        speed = -static_cast<int16_t>(MAX_SPEED);
    }

    if (speed > 0 && !frontMotionAllowed()) {
        writeMotor(motor, 0);
        return;
    }
    if (watchdogExpired || driverFaulted()) {
        stop();
        return;
    }
    writeMotor(motor, speed);
}

void MotorManager::setAll(int16_t speed) {
    if (speed == 0) {
        stop();
        return;
    }
    if (speed > 0 && !frontMotionAllowed()) {
        stop();
        return;
    }
    if (watchdogExpired || driverFaulted()) {
        stop();
        return;
    }
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        writeMotor(motor, speed);
    }
}

void MotorManager::notePiMessage() {
    lastPiMessageMs = millis();
    watchdogExpired = false;
}

void MotorManager::stop() {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        analogWrite(IN1_PINS[motor], 0);
        analogWrite(IN2_PINS[motor], 0);
        currentSpeed[motor] = 0;
    }
    // Shared nSLEEP low disables all four H-bridges independently of Pi code.
    digitalWrite(SLEEP_PIN, LOW);
}

bool MotorManager::isFaulted() const {
    return watchdogExpired || driverFaulted();
}

uint32_t MotorManager::encoderCount(uint8_t motor) const {
    if (motor >= MOTOR_COUNT) {
        return 0;
    }
    return encoderCounts[motor];
}

bool MotorManager::frontMotionAllowed() const {
    if (tof == nullptr) {
        return false;
    }
    for (uint8_t i = 0; i < ToFManager::SENSOR_COUNT; ++i) {
        const ToFManager::SensorId sensor = FRONT_SENSORS[i];
        if (!tof->isFresh(sensor) || !tof->isValid(sensor) ||
            tof->isObstacleDetected(sensor)) {
            return false;
        }
    }
    return true;
}

bool MotorManager::driverFaulted() const {
    // Both active-low, open-drain nFAULT outputs are wire-ORed on this input.
    return digitalRead(FAULT_PIN) == LOW;
}

void MotorManager::writeMotor(uint8_t motor, int16_t speed) {
    if (speed == 0) {
        analogWrite(IN1_PINS[motor], 0);
        analogWrite(IN2_PINS[motor], 0);
        currentSpeed[motor] = 0;
        return;
    }

    digitalWrite(SLEEP_PIN, HIGH);
    const uint8_t duty = static_cast<uint8_t>(speed < 0 ? -speed : speed);
    // Set the opposite input low before applying PWM to avoid a direction
    // crossover pulse when a wheel changes direction.
    analogWrite(IN1_PINS[motor], 0);
    analogWrite(IN2_PINS[motor], 0);
    if (speed > 0) {
        analogWrite(IN1_PINS[motor], duty);
    } else {
        analogWrite(IN2_PINS[motor], duty);
    }
    currentSpeed[motor] = speed;
}

void IRAM_ATTR MotorManager::encoder0ISR() { ++encoderCounts[0]; }
void IRAM_ATTR MotorManager::encoder1ISR() { ++encoderCounts[1]; }
void IRAM_ATTR MotorManager::encoder2ISR() { ++encoderCounts[2]; }
void IRAM_ATTR MotorManager::encoder3ISR() { ++encoderCounts[3]; }
