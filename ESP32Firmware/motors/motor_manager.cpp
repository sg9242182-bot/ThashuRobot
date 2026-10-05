#include "motor_manager.h"

#include <Arduino.h>

namespace {
constexpr uint8_t IN1_PINS[4] = {13, 27, 25, 19};
constexpr uint8_t IN2_PINS[4] = {14, 26, 23, 18};
constexpr uint8_t SLEEP_PIN = 32;
constexpr uint8_t ENCODER_PINS[4] = {33, 35, 39, 15};
}

volatile uint32_t MotorManager::encoderCounts[4] = {0, 0, 0, 0};

bool MotorManager::begin() {
    pinMode(SLEEP_PIN, OUTPUT);
    digitalWrite(SLEEP_PIN, LOW);
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
    stop();
    return true;
}

void MotorManager::setMotor(uint8_t motor, int16_t speed) {
    if (motor >= MOTOR_COUNT) return;
    if (speed > static_cast<int16_t>(MAX_SPEED)) speed = MAX_SPEED;
    else if (speed < -static_cast<int16_t>(MAX_SPEED)) speed = -MAX_SPEED;
    writeMotor(motor, speed);
}

void MotorManager::setAll(int16_t speed) {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) setMotor(motor, speed);
}

void MotorManager::stop() {
    for (uint8_t motor = 0; motor < MOTOR_COUNT; ++motor) {
        analogWrite(IN1_PINS[motor], 0);
        analogWrite(IN2_PINS[motor], 0);
    }
    digitalWrite(SLEEP_PIN, LOW);
}

uint32_t MotorManager::encoderCount(uint8_t motor) const {
    return motor < MOTOR_COUNT ? encoderCounts[motor] : 0;
}

void MotorManager::writeMotor(uint8_t motor, int16_t speed) {
    if (speed == 0) {
        analogWrite(IN1_PINS[motor], 0);
        analogWrite(IN2_PINS[motor], 0);
        return;
    }
    digitalWrite(SLEEP_PIN, HIGH);
    const uint8_t duty = static_cast<uint8_t>(speed < 0 ? -speed : speed);
    analogWrite(IN1_PINS[motor], 0);
    analogWrite(IN2_PINS[motor], 0);
    if (speed > 0) analogWrite(IN1_PINS[motor], duty);
    else analogWrite(IN2_PINS[motor], duty);
}

void IRAM_ATTR MotorManager::encoder0ISR() { ++encoderCounts[0]; }
void IRAM_ATTR MotorManager::encoder1ISR() { ++encoderCounts[1]; }
void IRAM_ATTR MotorManager::encoder2ISR() { ++encoderCounts[2]; }
void IRAM_ATTR MotorManager::encoder3ISR() { ++encoderCounts[3]; }
