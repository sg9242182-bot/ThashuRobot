#include "../motors/motor_manager.h"
#include "../safetymanager/safety_manager.h"
#include "../communicationmanager/communication_manager.h"
#include "../sensors/tof_manager/tof_manager.h"
#include "../sensors/ultrasonic_manager/ultrasonic_manager.h"
#include "../eyes/eye_manager.h"
#include "../servomanager/servo_manager.h"

#include <Arduino.h>

MotorManager motors;
ToFManager frontTof;
UltrasonicManager rearUltrasonic;
SafetyManager safety;
CommunicationManager communication;
EyeManager eyes;
ServoManager servos;

void setup() {
    Serial.begin(115200);
    Serial.println("EVENT|0|BOOT");
    if (!motors.begin()) {
        Serial.println("FAULT|0|MOTOR|INIT");
        while (true) { motors.stop(); delay(100); }
    }
    if (!eyes.begin()) {
        Serial.println("FAULT|0|OLED|INIT");
        while (true) { motors.stop(); delay(100); }
    }
    if (!servos.begin()) {
        Serial.println("FAULT|0|SERVO|INIT");
        while (true) { motors.stop(); delay(100); }
    }
    if (!safety.begin(motors, frontTof, rearUltrasonic, eyes, servos)) {
        Serial.println("FAULT|0|SAFETY|SENSOR_INIT");
        while (true) { motors.stop(); delay(100); }
    }
    eyes.setExpression(EXPR_IDLE);
    communication.begin(motors, safety, eyes, servos, frontTof, rearUltrasonic);
}

void loop() {
    safety.update();
    servos.update();
    eyes.update();
    communication.update();
}
