#include "communication_manager.h"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

namespace {
bool parseLong(const char* text, long& value) {
    if (!text || !*text) return false;
    char* end = nullptr;
    value = strtol(text, &end, 10);
    return *end == '\0';
}
}

void CommunicationManager::begin(MotorManager& motorManager, SafetyManager& safetyManager,
                                  EyeManager& eyeManager, ServoManager& servoManager) {
    motors = &motorManager; safety = &safetyManager; eyes = &eyeManager; servos = &servoManager;
    Serial.println("EVENT|0|BOOT");
    Serial.println("EVENT|0|READY");
}

void CommunicationManager::reportFault(const char* subsystem, const char* detail) {
    Serial.print("FAULT|0|"); Serial.print(subsystem); Serial.print('|'); Serial.println(detail);
}

void CommunicationManager::acknowledge(long sequence, const char* result) {
    Serial.print("ACK|"); Serial.print(sequence); Serial.print('|'); Serial.println(result);
}

void CommunicationManager::handle(char* line) {
    char* save = nullptr;
    char* field[7] = {};
    uint8_t count = 0;
    for (char* token = strtok_r(line, "|", &save); token && count < 7;
         token = strtok_r(nullptr, "|", &save)) field[count++] = token;
    if (count < 3 || strcmp(field[0], "CMD") != 0) return;
    long sequence;
    if (!parseLong(field[1], sequence) || sequence < 0) return;

    if (!strcmp(field[2], "STOP") && count == 3) {
        safety->notePiFrame(); motors->stop(); safety->setActiveMotion(SafetyManager::STOPPED, 0);
        acknowledge(sequence, "OK"); return;
    }
    if (!strcmp(field[2], "HEARTBEAT") && count == 3) {
        safety->notePiFrame(); acknowledge(sequence, "ALIVE"); return;
    }
    safety->notePiFrame();
    if (!strcmp(field[2], "MOTOR") && count == 5) {
        long speed;
        if (!parseLong(field[4], speed) || speed < 0 || speed > 255) {
            acknowledge(sequence, "ERROR|OUT_OF_RANGE"); return;
        }
        const bool forward = !strcmp(field[3], "FORWARD");
        const bool reverse = !strcmp(field[3], "BACKWARD");
        const bool left = !strcmp(field[3], "LEFT");
        const bool right = !strcmp(field[3], "RIGHT");
        if (!forward && !reverse && !left && !right) {
            acknowledge(sequence, "ERROR|INVALID_ARGUMENT"); return;
        }
        const SafetyManager::Motion motion = (left || right) ? SafetyManager::TURNING :
            (forward ? SafetyManager::FORWARD : SafetyManager::REVERSE);
        if (!safety->allowMotion(motion, (uint8_t)speed)) {
            motors->stop(); safety->setActiveMotion(SafetyManager::STOPPED, 0);
            acknowledge(sequence, "ERROR|SAFETY_STOP"); return;
        }
        if (speed == 0) motors->stop();
        else if (forward) motors->setAll(speed);
        else if (reverse) motors->setAll(-speed);
        else if (left) {
            motors->setMotor(0,-speed); motors->setMotor(1,speed);
            motors->setMotor(2,-speed); motors->setMotor(3,speed);
        } else {
            motors->setMotor(0,speed); motors->setMotor(1,-speed);
            motors->setMotor(2,speed); motors->setMotor(3,-speed);
        }
        safety->setActiveMotion(motion, (uint8_t)speed);
        acknowledge(sequence, "OK"); return;
    }
    if (!strcmp(field[2], "EYES") && count == 4) {
        if (!strcmp(field[3],"IDLE")) eyes->setExpression(EXPR_IDLE);
        else if (!strcmp(field[3],"HAPPY")) eyes->setExpression(EXPR_HAPPY);
        else if (!strcmp(field[3],"THINKING") || !strcmp(field[3],"LISTENING")) eyes->setExpression(EXPR_CURIOUS);
        else if (!strcmp(field[3],"SPEAKING")) eyes->setExpression(EXPR_HAPPY);
        else if (!strcmp(field[3],"ALERT")) eyes->setExpression(EXPR_ANGRY);
        else if (!strcmp(field[3],"SLEEP")) eyes->setExpression(EXPR_SLEEPY);
        else { acknowledge(sequence, "ERROR|INVALID_ARGUMENT"); return; }
        acknowledge(sequence, "OK"); return;
    }
    if (!strcmp(field[2], "SERVO") && count == 5 && !strcmp(field[3],"PAN_TILT")) {
        long pan, tilt;
        if (!parseLong(field[4], pan)) { acknowledge(sequence, "ERROR|INVALID_ARGUMENT"); return; }
        // Legacy Pi payload has four frame fields after CMD: PAN_TILT, PAN, TILT.
        char* tiltText = strtok_r(nullptr, "|", &save);
        if (!parseLong(tiltText, tilt) || pan < 0 || pan > 180 || tilt < 0 || tilt > 180) {
            acknowledge(sequence, "ERROR|OUT_OF_RANGE"); return;
        }
        servos->track(pan, tilt); acknowledge(sequence, "OK"); return;
    }
    if (!strcmp(field[2], "ENCODERS") && count == 3) {
        Serial.print("ENC|"); Serial.print(sequence);
        for (uint8_t i = 0; i < 4; ++i) { Serial.print('|'); Serial.print(motors->encoderCount(i)); }
        Serial.println(); return;
    }
    acknowledge(sequence, "ERROR|INVALID_COMMAND");
}

void CommunicationManager::readCommands() {
    size_t consumed = 0;
    while (Serial.available() && consumed++ < COMMAND_BUFFER_SIZE) {
        const char c = (char)Serial.read();
        if (c == '\n') {
            if (!discardingCommand && commandLength) {
                commandBuffer[commandLength] = '\0';
                if (commandLength && commandBuffer[commandLength-1] == '\r') commandBuffer[commandLength-1] = '\0';
                handle(commandBuffer);
            }
            commandLength = 0; discardingCommand = false;
        } else if (!discardingCommand) {
            if (commandLength + 1 >= COMMAND_BUFFER_SIZE) { commandLength = 0; discardingCommand = true; }
            else commandBuffer[commandLength++] = c;
        }
    }
}

void CommunicationManager::sendTelemetry() {
    if (millis() - lastTelemetryMs < 50) return;
    lastTelemetryMs = millis();
    const ToFManager& tof = *reinterpret_cast<ToFManager*>(nullptr);
    (void)tof;
}

void CommunicationManager::update() {
    readCommands();
}
