#include "tof_manager.h"

#include <Arduino.h>
#include <Wire.h>

namespace {
constexpr uint8_t XSHUT_PINS[ToFManager::SENSOR_COUNT] = {4, 16, 17};
constexpr uint8_t I2C_ADDRESSES[ToFManager::SENSOR_COUNT] = {0x30, 0x31, 0x32};
constexpr uint8_t OUT_OF_RANGE_STATUS = 4;
}

bool ToFManager::begin() {
    Wire.begin(SDA_PIN, SCL_PIN);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        pinMode(XSHUT_PINS[i], OUTPUT);
        digitalWrite(XSHUT_PINS[i], LOW);
        hasData[i] = false;
        valid[i] = false;
        obstacleDetected[i] = false;
        distanceMm[i] = 0;
        rangeStatus[i] = 255;
    }
    delay(STARTUP_DELAY_MS);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!initializeSensor(static_cast<SensorId>(i), XSHUT_PINS[i], I2C_ADDRESSES[i])) {
            return false;
        }
    }

    // Start all sensors in timed continuous mode. This starts measurements
    // without making update() wait for each ranging operation to finish.
    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        sensors[i].startRangeContinuous(CONTINUOUS_PERIOD_MS);
    }

    return true;
}

bool ToFManager::initializeSensor(SensorId sensor, uint8_t xshutPin, uint8_t address) {
    const uint8_t index = static_cast<uint8_t>(sensor);

    digitalWrite(xshutPin, HIGH);
    delay(STARTUP_DELAY_MS);

    if (!sensors[index].begin(0x29, false, &Wire)) {
        return false;
    }

    if (!sensors[index].setAddress(address)) {
        return false;
    }

    delay(STARTUP_DELAY_MS);
    return true;
}

void ToFManager::update() {
    // Non-blocking: only read a sensor when its continuous measurement is ready.
    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!sensors[i].isRangeComplete()) {
            continue;
        }

        const uint16_t measuredDistance = sensors[i].readRangeResult();
        const uint8_t status = sensors[i].readRangeStatus();

        rangeStatus[i] = status;

        // Adafruit returns 0xFFFF for the out-of-range/phase-failure case.
        if (status == OUT_OF_RANGE_STATUS || measuredDistance == 0xFFFFU) {
            hasData[i] = false;
            valid[i] = false;
            obstacleDetected[i] = false;
            distanceMm[i] = 0;
            continue;
        }

        hasData[i] = true;
        distanceMm[i] = measuredDistance;

        // Only a status-0 measurement is considered trustworthy for safety.
        // Other statuses remain available for diagnostics but cannot trigger
        // obstacle protection.
        valid[i] = (status == 0);
        obstacleDetected[i] = valid[i] &&
            distanceMm[i] <= static_cast<uint16_t>(OBSTACLE_DISTANCE_CM) * 10U;
    }
}

uint16_t ToFManager::getDistanceMm(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT ? distanceMm[index] : 0;
}

float ToFManager::getDistanceCm(SensorId sensor) const {
    return static_cast<float>(getDistanceMm(sensor)) / 10.0f;
}

bool ToFManager::hasReading(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && hasData[index];
}

bool ToFManager::isValid(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && valid[index];
}

bool ToFManager::isObstacleDetected(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && obstacleDetected[index];
}

uint8_t ToFManager::getRangeStatus(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT ? rangeStatus[index] : 255;
}
