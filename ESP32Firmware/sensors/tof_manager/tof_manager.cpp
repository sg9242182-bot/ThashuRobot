#include "tof_manager.h"

#include <Arduino.h>
#include <Wire.h>

namespace {
constexpr uint8_t XSHUT_PINS[ToFManager::SENSOR_COUNT] = {4, 16, 17};
constexpr uint8_t I2C_ADDRESSES[ToFManager::SENSOR_COUNT] = {0x30, 0x31, 0x32};
}

bool ToFManager::begin() {
    Wire.begin(SDA_PIN, SCL_PIN);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        pinMode(XSHUT_PINS[i], OUTPUT);
        digitalWrite(XSHUT_PINS[i], LOW);
        valid[i] = false;
        obstacleDetected[i] = false;
        distanceMm[i] = 0;
    }
    delay(STARTUP_DELAY_MS);

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        if (!initializeSensor(static_cast<SensorId>(i), XSHUT_PINS[i], I2C_ADDRESSES[i])) {
            return false;
        }
    }

    lastMeasurementTime = millis();
    return true;
}

bool ToFManager::initializeSensor(SensorId sensor, uint8_t xshutPin, uint8_t address) {
    const uint8_t index = static_cast<uint8_t>(sensor);

    digitalWrite(xshutPin, HIGH);
    delay(STARTUP_DELAY_MS);

    if (!sensors[index].begin(0x29, false, &Wire)) {
        return false;
    }

    sensors[index].setAddress(address);
    delay(STARTUP_DELAY_MS);
    return true;
}

void ToFManager::update() {
    const unsigned long now = millis();
    if (now - lastMeasurementTime < MEASUREMENT_INTERVAL_MS) {
        return;
    }
    lastMeasurementTime = now;

    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        VL53L0X_RangingMeasurementData_t measurement;
        sensors[i].rangingTest(&measurement, false);

        if (measurement.RangeStatus == 0) {
            distanceMm[i] = measurement.RangeMilliMeter;
            valid[i] = true;
            obstacleDetected[i] = distanceMm[i] <= static_cast<uint16_t>(OBSTACLE_DISTANCE_CM) * 10U;
        } else {
            valid[i] = false;
            obstacleDetected[i] = false;
        }
    }
}

uint16_t ToFManager::getDistanceMm(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT ? distanceMm[index] : 0;
}

float ToFManager::getDistanceCm(SensorId sensor) const {
    return static_cast<float>(getDistanceMm(sensor)) / 10.0f;
}

bool ToFManager::isValid(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && valid[index];
}

bool ToFManager::isObstacleDetected(SensorId sensor) const {
    const uint8_t index = static_cast<uint8_t>(sensor);
    return index < SENSOR_COUNT && obstacleDetected[index];
}
