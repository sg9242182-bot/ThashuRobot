#pragma once

#include <Arduino.h>
#include <stdint.h>
#include "../sensors/tof_manager/tof_manager.h"

class MotorManager {
public:
    bool begin(ToFManager& frontTof);

    void update();

    // Speed: -255 to +255
    // Positive = forward
    // Negative = reverse
    // Zero = stop
    void setMotor(uint8_t motor, int16_t speed);

    void setAll(int16_t speed);

    // Call for every valid Pi protocol frame, including HEARTBEAT and STOP.
    void notePiMessage();

    void stop();

    bool isFaulted() const;
    uint32_t encoderCount(uint8_t motor) const;

private:
    static constexpr uint8_t MOTOR_COUNT = 4;
    static constexpr unsigned long PI_WATCHDOG_MS = 500;
    static constexpr uint8_t MAX_SPEED = 255;

    static volatile uint32_t encoderCounts[MOTOR_COUNT];

    ToFManager* tof = nullptr;
    unsigned long lastPiMessageMs = 0;
    bool watchdogExpired = true;
    int16_t currentSpeed[MOTOR_COUNT] = {0, 0, 0, 0};

    bool frontMotionAllowed() const;
    bool driverFaulted() const;
    void writeMotor(uint8_t motor, int16_t speed);
    static void IRAM_ATTR encoder0ISR();
    static void IRAM_ATTR encoder1ISR();
    static void IRAM_ATTR encoder2ISR();
    static void IRAM_ATTR encoder3ISR();
};
