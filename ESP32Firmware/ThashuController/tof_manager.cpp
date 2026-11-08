#include "tof_manager.h"

#include <Arduino.h>
#include <Wire.h>

bool ToFManager::selectMuxChannel(uint8_t channel) {
    if (channel > 7) return false;
    Wire.beginTransmission(MUX_ADDRESS);
    Wire.write(static_cast<uint8_t>(1U << channel));
    return Wire.endTransmission() == 0;
}

bool ToFManager::deselectMux() {
    Wire.beginTransmission(MUX_ADDRESS);
    Wire.write(static_cast<uint8_t>(0));
    return Wire.endTransmission() == 0;
}

bool ToFManager::begin() {
    Wire.begin(SDA_PIN, SCL_PIN);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        hasData[i] = false;
        outOfRange[i] = false;
        valid[i] = false;
        obstacleDetected[i] = false;
        distanceMm[i] = 0;
        rangeStatus[i] = 255;
        lastReadingTime[i] = 0;
    }

    // Keep the parent I2C bus isolated from all mux channels while the three
    // front sensors are brought up and assigned their existing addresses.
    if (!deselectMux()) return false;

    for (uint8_t i = 0; i < 3; ++i) {
        pinMode(FRONT_XSHUT_PINS[i], OUTPUT);
        digitalWrite(FRONT_XSHUT_PINS[i], LOW);
    }
    delay(STARTUP_DELAY_MS);

    for (uint8_t i = 0; i < 3; ++i) {
        if (!initializeFrontSensor(static_cast<SensorId>(i),
                                   FRONT_XSHUT_PINS[i],
                                   FRONT_I2C_ADDRESSES[i])) {
            deselectMux();
            return false;
        }
    }

    // Each rear sensor stays at its default 0x29 address on a dedicated mux
    // channel, so no rear XSHUT wiring or address reassignment is required.
    for (uint8_t i = 0; i < 3; ++i) {
        if (!initializeRearSensor(static_cast<SensorId>(REAR_LEFT + i),
                                  REAR_MUX_CHANNELS[i])) {
            deselectMux();
            return false;
        }
    }

    if (!deselectMux()) return false;
    for (uint8_t i = 0; i < 3; ++i) {
        sensors[i].startRangeContinuous(CONTINUOUS_PERIOD_MS);
    }
    for (uint8_t i = 0; i < 3; ++i) {
        if (!selectMuxChannel(REAR_MUX_CHANNELS[i])) return false;
        sensors[REAR_LEFT + i].startRangeContinuous(CONTINUOUS_PERIOD_MS);
    }
    return deselectMux();
}

bool ToFManager::initializeFrontSensor(SensorId sensor, uint8_t xshutPin,
                                       uint8_t address) {
    const uint8_t index = static_cast<uint8_t>(sensor);
    digitalWrite(xshutPin, HIGH);
    delay(STARTUP_DELAY_MS);

    if (!sensors[index].begin(0x29, false, &Wire)) return false;
    if (!sensors[index].setAddress(address)) return false;
    delay(STARTUP_DELAY_MS);
    return true;
}

bool ToFManager::initializeRearSensor(SensorId sensor, uint8_t muxChannel) {
    if (!selectMuxChannel(muxChannel)) return false;
    delay(STARTUP_DELAY_MS);
    return sensors[static_cast<uint8_t>(sensor)].begin(0x29, false, &Wire);
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
    // Front sensors are directly on the parent bus; disconnect all mux
    // channels before accessing them.
    if (!deselectMux()) return;
    for (uint8_t i = 0; i < 3; ++i) {
        updateSensor(static_cast<SensorId>(i));
    }

    // Select one rear sensor at a time. The three modules can all retain their
    // default 0x29 I2C address because only one downstream channel is visible.
    for (uint8_t i = 0; i < 3; ++i) {
        if (!selectMuxChannel(REAR_MUX_CHANNELS[i])) continue;
        updateSensor(static_cast<SensorId>(REAR_LEFT + i));
    }
    deselectMux();
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
