#include "safety_manager.h"

namespace {
constexpr ToFManager::SensorId FRONT_IDS[3] = {
    ToFManager::FRONT_LEFT, ToFManager::FRONT_CENTER, ToFManager::FRONT_RIGHT
};
}

bool SafetyManager::begin(MotorManager& motorManager, ToFManager& frontTof,
                          UltrasonicManager& rearUltrasonic) {
    motors = &motorManager;
    tof = &frontTof;
    rear = &rearUltrasonic;
    pinMode(DRIVER_FAULT_PIN, INPUT);
    motors->stop();
    if (!tof->begin()) return false;
    if (!rear->begin()) return false;
    lastPiFrameMs = millis();
    watchdogExpired = true;
    initialized = true;
    return true;
}

void SafetyManager::notePiFrame() {
    lastPiFrameMs = millis();
    watchdogExpired = false;
}

bool SafetyManager::frontClear() const {
    if (!tof) return false;
    for (uint8_t i = 0; i < 3; ++i) {
        if (!tof->isFresh(FRONT_IDS[i]) || !tof->isValid(FRONT_IDS[i]) ||
            tof->isObstacleDetected(FRONT_IDS[i])) return false;
    }
    return true;
}

bool SafetyManager::rearClear() const {
    return rear && rear->isFresh() && rear->isValid() &&
           !rear->isObstacleDetected();
}

bool SafetyManager::allowMotion(Motion motion, uint8_t speed) const {
    if (speed == 0 || motion == STOPPED) return true;
    if (!initialized || watchdogExpired || driverFaulted()) return false;
    if ((motion == FORWARD || motion == TURNING) && !frontClear()) return false;
    if ((motion == REVERSE || motion == TURNING) && !rearClear()) return false;
    return true;
}

void SafetyManager::update() {
    if (!initialized || !motors) return;
    tof->update();
    rear->update();
    if (millis() - lastPiFrameMs >= PI_WATCHDOG_MS) watchdogExpired = true;
    if (watchdogExpired || driverFaulted() ||
        (activeMotion != STOPPED &&
         !allowMotion(activeMotion, 1))) {
        motors->stop();
        activeMotion = STOPPED;
    }
}

bool SafetyManager::driverFaulted() const {
    return digitalRead(DRIVER_FAULT_PIN) == LOW;
}

void SafetyManager::setActiveMotion(Motion motion, uint8_t speed) {
    activeMotion = speed == 0 ? STOPPED : motion;
}

bool SafetyManager::ready() const { return initialized; }
