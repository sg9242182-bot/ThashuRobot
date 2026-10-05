#pragma once

#include <Arduino.h>
#include <stdint.h>

// Owns DRV8833 input pins and encoder pulse counts only.
// Safety decisions and Pi communication belong to their dedicated managers.
class MotorManager {
public:
    bool begin();
    void setMotor(uint8_t motor, int16_t speed);
    void setAll(int16_t speed);
    void stop();
    uint32_t encoderCount(uint8_t motor) const;

private:
    static constexpr uint8_t MOTOR_COUNT = 4;
    static constexpr uint8_t MAX_SPEED = 255;
    static volatile uint32_t encoderCounts[MOTOR_COUNT];
    void writeMotor(uint8_t motor, int16_t speed);
    static void IRAM_ATTR encoder0ISR();
    static void IRAM_ATTR encoder1ISR();
    static void IRAM_ATTR encoder2ISR();
    static void IRAM_ATTR encoder3ISR();
};
