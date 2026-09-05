#pragma once

#include <stdint.h>
#include <Adafruit_VL53L0X.h>

class ToFManager {
public:
    enum SensorId : uint8_t {
        FRONT_LEFT = 0,
        FRONT_CENTER = 1,
        FRONT_RIGHT = 2,
        SENSOR_COUNT = 3,
    };

    bool begin();
    void update();

    uint16_t getDistanceMm(SensorId sensor) const;
    float getDistanceCm(SensorId sensor) const;
    bool isValid(SensorId sensor) const;
    bool isObstacleDetected(SensorId sensor) const;

private:
    static constexpr uint8_t SDA_PIN = 21;
    static constexpr uint8_t SCL_PIN = 22;
    static constexpr uint8_t XSHUT_PINS[SENSOR_COUNT] = {4, 16, 17};
    static constexpr uint8_t I2C_ADDRESSES[SENSOR_COUNT] = {0x30, 0x31, 0x32};

    static constexpr unsigned long STARTUP_DELAY_MS = 10;
    static constexpr unsigned long MEASUREMENT_INTERVAL_MS = 60;
    static constexpr uint16_t OBSTACLE_DISTANCE_MM = 300;

    Adafruit_VL53L0X sensors[SENSOR_COUNT];
    uint16_t distanceMm[SENSOR_COUNT] = {0, 0, 0};
    bool valid[SENSOR_COUNT] = {false, false, false};
    bool obstacleDetected[SENSOR_COUNT] = {false, false, false};
    unsigned long lastMeasurementTime = 0;

    bool initializeSensor(SensorId sensor);
};
