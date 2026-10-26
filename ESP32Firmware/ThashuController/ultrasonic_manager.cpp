#include "ultrasonic_manager.h"

#include <Arduino.h>

UltrasonicManager* UltrasonicManager::instance = nullptr;

bool UltrasonicManager::begin() {
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);

    digitalWrite(TRIG_PIN, LOW);

    instance = this;

    attachInterrupt(
        digitalPinToInterrupt(ECHO_PIN),
        echoISR,
        CHANGE
    );

    delay(50);

    lastMeasurementTime = millis();

    return true;
}

void UltrasonicManager::update() {
    unsigned long now = millis();

    /*
     * First, check whether the ISR has completed
     * an echo pulse.
     */
    if (echoComplete) {
        noInterrupts();

        unsigned long duration = echoDuration;

        echoComplete = false;
        echoStarted = false;

        interrupts();

        float measured = processEchoDuration(duration);
        lastReadingTime = millis();
        hasReading = true;

        if (measured >= 2.0f && measured <= 400.0f) {
            distanceCm = measured;
            valid = true;
            outOfRange = false;
            obstacleDetected = (distanceCm <= OBSTACLE_DISTANCE_CM);
        } else if (measured > 400.0f) {
            valid = false;
            outOfRange = true;
            obstacleDetected = false;
        } else {
            valid = false;
            outOfRange = false;
            obstacleDetected = false;
        }

        waitingForEcho = false;
    }

    /*
     * Start a new measurement when the required
     * interval has elapsed.
     */
    if (!waitingForEcho &&
        (now - lastMeasurementTime >= MEASUREMENT_INTERVAL_MS)) {

        lastMeasurementTime = now;

        noInterrupts();

        echoStarted = false;
        echoComplete = false;

        interrupts();

        measurementStartTime = micros();

        waitingForEcho = true;

        triggerMeasurement();
    }

    /*
     * Timeout handling.
     *
     * This 40 ms timeout is measured from the trigger.
     * It allows the HC-SR04's 38 ms no-target pulse to
     * finish and be classified as FAR before timeout.
     * A pulse that remains high beyond this is malformed.
     */
    if (waitingForEcho &&
        (micros() - measurementStartTime >= ECHO_TIMEOUT_US)) {

        noInterrupts();

        const bool sawRisingEdge = echoStarted;
        waitingForEcho = false;
        echoStarted = false;
        echoComplete = false;

        interrupts();

        lastReadingTime = millis();
        hasReading = true;
        valid = false;
        // No pulse at all is a fresh no-echo / out-of-range result. A pulse
        // that started but never ended is malformed and remains SENSOR_NOT_READY.
        outOfRange = !sawRisingEdge;
        obstacleDetected = false;
    }
}

void UltrasonicManager::triggerMeasurement() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
}

float UltrasonicManager::processEchoDuration(
    unsigned long duration) {

    if (duration == 0) {
        return 0.0f;
    }

    float distance = duration / 58.0f;

    return distance;
}

void IRAM_ATTR UltrasonicManager::echoISR() {
    if (instance == nullptr) {
        return;
    }

    if (digitalRead(ECHO_PIN) == HIGH) {

        /*
         * Rising edge:
         * ultrasonic echo pulse has started.
         */
        instance->echoStartTime = micros();
        instance->echoStarted = true;

    } else {

        /*
         * Falling edge:
         * ultrasonic echo pulse has ended.
         */
        if (instance->echoStarted) {

            unsigned long endTime = micros();

            instance->echoDuration =
                endTime - instance->echoStartTime;

            instance->echoComplete = true;
        }
    }
}

bool UltrasonicManager::isFresh() const {
    return hasReading && millis() - lastReadingTime <= 200;
}

float UltrasonicManager::getDistanceCm() const {
    return distanceCm;
}

bool UltrasonicManager::isValid() const {
    return valid;
}

bool UltrasonicManager::isOutOfRange() const {
    return outOfRange;
}

bool UltrasonicManager::isObstacleDetected() const {
    return obstacleDetected;
}