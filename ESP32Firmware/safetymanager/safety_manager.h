#pragma once

#include <Arduino.h>
#include <stdint.h>
#include "../motors/motor_manager.h"
#include "../sensors/tof_manager/tof_manager.h"
#include "../sensors/ultrasonic_manager/ultrasonic_manager.h"

// Robot reflex layer: validates requested movement and forces STOP on hazards,
// stale Pi traffic, or the shared active-low driver fault signal.
class SafetyManager {
public:
    enum Motion : uint8_t { STOPPED, FORWARD, REVERSE, TURNING };
    bool begin(MotorManager& motors, ToFManager& frontTof, UltrasonicManager& rearUltrasonic);
    void update();
    void notePiFrame();
    bool allowMotion(Motion motion, uint8_t speed) const;
    void setActiveMotion(Motion motion, uint8_t speed);
    bool driverFaulted() const;
    bool ready() const;

private:
    static constexpr uint8_t DRIVER_FAULT_PIN = 34;
    static constexpr unsigned long PI_WATCHDOG_MS = 500;
    static constexpr unsigned long REAR_READING_MAX_AGE_MS = 200;
    MotorManager* motors = nullptr;
    ToFManager* tof = nullptr;
    UltrasonicManager* rear = nullptr;
    unsigned long lastPiFrameMs = 0;
    bool watchdogExpired = true;
    bool initialized = false;
    Motion activeMotion = STOPPED;
    bool frontClear() const;
    bool rearClear() const;
};
