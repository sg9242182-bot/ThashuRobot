#pragma once

#include <stdint.h>

class UltrasonicManager {
public:
    bool begin();
    void update();

    float getDistanceCm() const;
    bool isValid() const;
    bool isFresh() const;
    bool isOutOfRange() const;
    bool isObstacleDetected() const;

private:
    // GPIO32 is output-capable and avoids the GPIO2 boot-strap pin.
    static constexpr uint8_t TRIG_PIN = 32;
    // Keep ECHO on the existing GPIO36 input through its voltage divider.
    static constexpr uint8_t ECHO_PIN = 36;

    static constexpr unsigned long MEASUREMENT_INTERVAL_MS = 60;
    static constexpr unsigned long ECHO_TIMEOUT_US = 25000;

    static constexpr float OBSTACLE_DISTANCE_CM = 30.0f;

    float distanceCm = 0.0f;
    bool valid = false;
    bool outOfRange = false;
    bool hasReading = false;
    bool obstacleDetected = false;

    unsigned long lastMeasurementTime = 0;
    unsigned long measurementStartTime = 0;
    unsigned long lastReadingTime = 0;

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
