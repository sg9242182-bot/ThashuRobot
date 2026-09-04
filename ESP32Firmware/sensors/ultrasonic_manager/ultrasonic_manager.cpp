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

        if (measured > 0.0f) {
            distanceCm = measured;
            valid = true;
            obstacleDetected =
                (distanceCm <= OBSTACLE_DISTANCE_CM);
        } else {
            valid = false;
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
     * This timeout is measured from the moment
     * we actually triggered the HC-SR04.
     *
     * Therefore it also works correctly when
     * NO rising edge is ever received.
     */
    if (waitingForEcho &&
        (micros() - measurementStartTime >= ECHO_TIMEOUT_US)) {

        noInterrupts();

        waitingForEcho = false;
        echoStarted = false;
        echoComplete = false;

        interrupts();

        valid = false;
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

    if (distance < 2.0f || distance > 400.0f) {
        return 0.0f;
    }

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

float UltrasonicManager::getDistanceCm() const {
    return distanceCm;
}

bool UltrasonicManager::isValid() const {
    return valid;
}

bool UltrasonicManager::isObstacleDetected() const {
    return obstacleDetected;
}