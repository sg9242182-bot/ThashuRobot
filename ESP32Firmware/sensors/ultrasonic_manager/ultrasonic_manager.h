#pragma once

#include <stdint.h>

class UltrasonicManager {
public:
    bool begin();
    void update();

    float getDistanceCm() const;
    bool isValid() const;
    bool isObstacleDetected() const;

private:
    static constexpr uint8_t TRIG_PIN = 2;
    static constexpr uint8_t ECHO_PIN = 36;

    static constexpr unsigned long MEASUREMENT_INTERVAL_MS = 60;
    static constexpr unsigned long ECHO_TIMEOUT_US = 25000;

    static constexpr float OBSTACLE_DISTANCE_CM = 30.0f;

    float distanceCm = 0.0f;
    bool valid = false;
    bool obstacleDetected = false;

    unsigned long lastMeasurementTime = 0;
    unsigned long measurementStartTime = 0;

    volatile unsigned long echoStartTime = 0;
    volatile unsigned long echoDuration = 0;
    volatile bool echoComplete = false;
    volatile bool echoStarted = false;

    bool waitingForEcho = false;

    float processEchoDuration(unsigned long duration);
    void triggerMeasurement();

    static void echoISR();
    static UltrasonicManager* instance;
};