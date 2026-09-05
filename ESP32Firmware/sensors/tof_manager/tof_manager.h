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
    bool hasReading(SensorId sensor) const;
    bool isValid(SensorId sensor) const;
    bool isObstacleDetected(SensorId sensor) const;
    uint8_t getRangeStatus(SensorId sensor) const;

private:
    static constexpr uint8_t SDA_PIN = 21;
    static constexpr uint8_t SCL_PIN = 22;
    static constexpr uint8_t OBSTACLE_DISTANCE_CM = 30;
    static constexpr unsigned long STARTUP_DELAY_MS = 10;
    static constexpr uint16_t CONTINUOUS_PERIOD_MS = 50;

    Adafruit_VL53L0X sensors[SENSOR_COUNT];
    uint16_t distanceMm[SENSOR_COUNT] = {0, 0, 0};
    uint8_t rangeStatus[SENSOR_COUNT] = {255, 255, 255};
    bool hasData[SENSOR_COUNT] = {false, false, false};
    bool valid[SENSOR_COUNT] = {false, false, false};
    bool obstacleDetected[SENSOR_COUNT] = {false, false, false};

    bool initializeSensor(SensorId sensor, uint8_t xshutPin, uint8_t address);
};
