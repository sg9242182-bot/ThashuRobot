#pragma once

#include <stdint.h>
#include <Adafruit_VL53L0X.h>

class ToFManager {
public:
    enum SensorId : uint8_t {
        FRONT_LEFT = 0,
        FRONT_CENTER = 1,
        FRONT_RIGHT = 2,
        REAR_LEFT = 3,
        REAR_CENTER = 4,
        REAR_RIGHT = 5,
        SENSOR_COUNT = 6,
    };

    bool begin();
    void update();

    uint16_t getDistanceMm(SensorId sensor) const;
    float getDistanceCm(SensorId sensor) const;
    bool hasReading(SensorId sensor) const;
    bool isValid(SensorId sensor) const;
    bool isFresh(SensorId sensor) const;
    bool isOutOfRange(SensorId sensor) const;
    bool isObstacleDetected(SensorId sensor) const;
    uint8_t getRangeStatus(SensorId sensor) const;

private:
    static constexpr uint8_t SDA_PIN = 21;
    static constexpr uint8_t SCL_PIN = 22;
    static constexpr uint8_t MUX_ADDRESS = 0x70;
    static constexpr uint8_t REAR_MUX_CHANNELS[3] = {0, 1, 2};
    static constexpr uint8_t FRONT_XSHUT_PINS[3] = {4, 16, 17};
    static constexpr uint8_t FRONT_I2C_ADDRESSES[3] = {0x30, 0x31, 0x32};
    static constexpr uint8_t OUT_OF_RANGE_STATUS = 4;
    static constexpr uint8_t OBSTACLE_DISTANCE_CM = 30;
    static constexpr unsigned long STARTUP_DELAY_MS = 10;
    static constexpr uint16_t CONTINUOUS_PERIOD_MS = 50;
    static constexpr unsigned long READING_MAX_AGE_MS = 150;

    Adafruit_VL53L0X sensors[SENSOR_COUNT];
    uint16_t distanceMm[SENSOR_COUNT] = {0, 0, 0, 0, 0, 0};
    uint8_t rangeStatus[SENSOR_COUNT] = {255, 255, 255, 255, 255, 255};
    bool hasData[SENSOR_COUNT] = {false, false, false, false, false, false};
    bool outOfRange[SENSOR_COUNT] = {false, false, false, false, false, false};
    bool valid[SENSOR_COUNT] = {false, false, false, false, false, false};
    bool obstacleDetected[SENSOR_COUNT] = {false, false, false, false, false, false};
    unsigned long lastReadingTime[SENSOR_COUNT] = {0, 0, 0, 0, 0, 0};

    bool selectMuxChannel(uint8_t channel);
    bool deselectMux();
    bool initializeFrontSensor(SensorId sensor, uint8_t xshutPin, uint8_t address);
    bool initializeRearSensor(SensorId sensor, uint8_t muxChannel);
    void updateSensor(SensorId sensor);
};
