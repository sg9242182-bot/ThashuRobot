#pragma once

#include <Arduino.h>
#include <stdint.h>
#include "motor_manager.h"
#include "tof_manager.h"
#include "eye_manager.h"
#include "servo_manager.h"

// Robot reflex layer: validates requested movement and forces STOP on hazards,
// stale sensors, required-hardware faults, or stale Pi traffic.
class SafetyManager {
public:
    enum Motion : uint8_t { STOPPED, FORWARD, REVERSE, TURNING };
    bool begin(MotorManager& motors, ToFManager& tof, EyeManager& eyes,
               ServoManager& servos);
    void update();
    void notePiFrame();
    bool allowMotion(Motion motion, uint8_t speed) const;
    void setActiveMotion(Motion motion, uint8_t speed);
    bool obstacleDetectedFor(Motion motion) const;
    bool consumeObstacleStop();
    bool ready() const;

private:
    static constexpr unsigned long PI_WATCHDOG_MS = 500;
    MotorManager* motors = nullptr;
    ToFManager* tof = nullptr;
    EyeManager* eyes = nullptr;
    ServoManager* servos = nullptr;
    bool requiredHardwareReady() const;
    unsigned long lastPiFrameMs = 0;
    bool watchdogExpired = true;
    bool initialized = false;
    bool obstacleStopPending = false;
    Motion activeMotion = STOPPED;
    bool frontClear() const;
    bool rearClear() const;
};
