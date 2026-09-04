#include "ultrasonic_manager.h"

UltrasonicManager ultrasonic;

unsigned long lastPrint = 0;

void setup() {
    Serial.begin(115200);

    delay(500);

    Serial.println();
    Serial.println("=== Thashu Ultrasonic Test ===");

    ultrasonic.begin();

    Serial.println("HC-SR04 initialized");
    Serial.println("TRIG = GPIO2");
    Serial.println("ECHO = GPIO36");
}

void loop() {
    ultrasonic.update();

    unsigned long now = millis();

    if (now - lastPrint >= 250) {
        lastPrint = now;

        Serial.print("Distance: ");

        if (ultrasonic.isValid()) {
            Serial.print(ultrasonic.getDistanceCm(), 1);
            Serial.print(" cm");

            if (ultrasonic.isObstacleDetected()) {
                Serial.print(" | REAR OBSTACLE");
            } else {
                Serial.print(" | CLEAR");
            }
        } else {
            Serial.print("INVALID / NO ECHO");
        }

        Serial.println();
    }
}