#include "tof_manager.h"

#include <Arduino.h>
#include <Wire.h>
#include "i2c_mux.h"

namespace {
constexpr uint8_t TOF_MUX_CHANNELS[ToFManager::SENSOR_COUNT] = {0, 1, 2, 3, 4, 5};
}

bool ToFManager::begin() {
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        hasData[i] = false;
        outOfRange[i] = false;
        valid[i] = false;
        obstacleDetected[i] = false;
        distanceMm[i] = 0;
        rangeStatus[i] = 255;
        lastReadingTime[i] = 0;
    }

    // Every ToF is isolated on its own mux channel, so all six can retain the
    // VL53L0X default address (0x29); XSHUT address sequencing is unnecessary.
    if (!deselectI2cMux()) return false;
    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!initializeSensor(static_cast<SensorId>(i), TOF_MUX_CHANNELS[i])) {
            deselectI2cMux();
            return false;
        }
    }

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!selectI2cMuxChannel(TOF_MUX_CHANNELS[i])) {
            deselectI2cMux();
            return false;
        }
        sensors[i].startRangeContinuous(CONTINUOUS_PERIOD_MS);
    }
    return deselectI2cMux();
}

bool ToFManager::initializeSensor(SensorId sensor, uint8_t muxChannel) {
    const uint8_t index = static_cast<uint8_t>(sensor);
    if (!selectI2cMuxChannel(muxChannel)) return false;
    delay(STARTUP_DELAY_MS);
    const bool ready = sensors[index].begin(0x29, false, &Wire);
    deselectI2cMux();
    return ready;
}

void ToFManager::updateSensor(SensorId sensor) {
    const uint8_t index = static_cast<uint8_t>(sensor);
    if (index >= SENSOR_COUNT || !sensors[index].isRangeComplete()) return;

    const uint16_t measuredDistance = sensors[index].readRangeResult();
    const uint8_t status = sensors[index].readRangeStatus();
    rangeStatus[index] = status;

    // Status 4 is the library's explicit no-target/out-of-range result.
    // readRangeResult() returns 0xFFFF for status 4, so classify it first.
    if (status == OUT_OF_RANGE_STATUS) {
        lastReadingTime[index] = millis();
        hasData[index] = true;
        outOfRange[index] = true;
        valid[index] = false;
        obstacleDetected[index] = false;
        distanceMm[index] = 0;
        return;
    }

    // A sentinel without status 4 means the I2C/API read failed. Preserve the
    // last successful sample; it still expires at READING_MAX_AGE_MS.
    if (measuredDistance == 0xFFFFU) return;

    lastReadingTime[index] = millis();
    hasData[index] = true;
    outOfRange[index] = false;
    distanceMm[index] = measuredDistance;

    const uint16_t obstacleThresholdMm =
        static_cast<uint16_t>(OBSTACLE_DISTANCE_CM) * 10U;
    const bool inObstacleZone = measuredDistance <= obstacleThresholdMm;

    // Weak returns above the stop threshold can be used for clear-path checks.
    // At or inside the threshold, retain fail-safe obstacle behavior.
    valid[index] = (status == 0) || (status == 2 && !inObstacleZone);
    obstacleDetected[index] =
        (status == 0 || status == 2) && inObstacleZone;
}

void ToFManager::update() {
    // Only one same-address ToF is exposed to the controller at a time.
    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!selectI2cMuxChannel(TOF_MUX_CHANNELS[i])) continue;
        updateSensor(static_cast<SensorId>(i));
    }
    deselectI2cMux();
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

bool ToFManager::isFresh(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && hasData[index] &&
        (millis() - lastReadingTime[index] <= READING_MAX_AGE_MS);
}

bool ToFManager::isOutOfRange(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && outOfRange[index];
}

bool ToFManager::isObstacleDetected(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && obstacleDetected[index];
}

uint8_t ToFManager::getRangeStatus(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT ? rangeStatus[index] : 255;
}
