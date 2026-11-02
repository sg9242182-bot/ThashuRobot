#include "communication_manager.h"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

constexpr long CommunicationManager::PROTOCOL_VERSION;

namespace {
bool parseLong(const char* text, long& value) {
    if (!text || !*text) return false;
    char* end = nullptr;
    value = strtol(text, &end, 10);
    return *end == '\0';
}

bool validSessionId(const char* sessionId) {
    if (!sessionId || strlen(sessionId) != 32) return false;
    for (const char* character = sessionId; *character; ++character) {
        const bool digit = *character >= '0' && *character <= '9';
        const bool lowerHex = *character >= 'a' && *character <= 'f';
        const bool upperHex = *character >= 'A' && *character <= 'F';
        if (!digit && !lowerHex && !upperHex) return false;
    }
    return true;
}
}

void CommunicationManager::begin(MotorManager& motorManager, SafetyManager& safetyManager,
                                  EyeManager& eyeManager, ServoManager& servoManager, ToFManager& tofManager, UltrasonicManager& rearUltrasonic) {
    motors = &motorManager; safety = &safetyManager; eyes = &eyeManager; servos = &servoManager; tof = &tofManager; rear = &rearUltrasonic;
    Serial.println("EVENT|1|0|READY");
    Serial.println("INFO|1|MOTOR_MAP|M0=Motor1(front-left)|M1=Motor2(rear-left)|M2=Motor3(front-right)|M3=Motor4(rear-right)");
}

void CommunicationManager::reportFault(const char* subsystem, const char* detail) {
    Serial.print("FAULT|1|0|"); Serial.print(subsystem); Serial.print('|'); Serial.println(detail);
}

void CommunicationManager::acknowledge(long version, const char* sessionId, long sequence, const char* result) {
    Serial.print("ACK|"); Serial.print(version); Serial.print('|');
    Serial.print(sessionId); Serial.print('|'); Serial.print(sequence); Serial.print('|');
    Serial.println(result);
}

void CommunicationManager::handle(char* line) {
    char* save = nullptr;
    char* field[10] = {};
    uint8_t count = 0;
    for (char* token = strtok_r(line, "|", &save); token && count < 10;
         token = strtok_r(nullptr, "|", &save)) field[count++] = token;
    if (count < 5 || strcmp(field[0], "CMD") != 0) return;

    long version, sequence;
    const char* sessionId = field[2];
    if (!parseLong(field[1], version) || !validSessionId(sessionId) ||
        !parseLong(field[3], sequence) || sequence < 1 || sequence > 0x7FFFFFFF) return;
    if (version != PROTOCOL_VERSION) {
        acknowledge(PROTOCOL_VERSION, sessionId, sequence, "ERROR|UNSUPPORTED_VERSION");
        return;
    }

    if (!strcmp(field[4], "STOP") && count == 5) {
        safety->notePiFrame(); motors->stop(); safety->setActiveMotion(SafetyManager::STOPPED, 0);
        acknowledge(version, sessionId, sequence, "OK"); return;
    }
    if (!strcmp(field[4], "HEARTBEAT") && count == 5) {
        safety->notePiFrame(); acknowledge(version, sessionId, sequence, "ALIVE"); return;
    }
    if (!strcmp(field[4], "MOTOR") && count == 7) {
        long speed;
        if (!parseLong(field[6], speed) || speed < 0 || speed > 255) {
            acknowledge(version, sessionId, sequence, "ERROR|OUT_OF_RANGE"); return;
        }
        const bool forward = !strcmp(field[5], "FORWARD");
        const bool reverse = !strcmp(field[5], "BACKWARD");
        const bool left = !strcmp(field[5], "LEFT");
        const bool right = !strcmp(field[5], "RIGHT");
        if (!forward && !reverse && !left && !right) {
            acknowledge(version, sessionId, sequence, "ERROR|INVALID_ARGUMENT"); return;
        }
        const SafetyManager::Motion motion = (left || right) ? SafetyManager::TURNING :
            (forward ? SafetyManager::FORWARD : SafetyManager::REVERSE);
        safety->notePiFrame();
        if (!safety->allowMotion(motion, (uint8_t)speed)) {
            const bool obstacleDetected = safety->obstacleDetectedFor(motion);
            motors->stop(); safety->setActiveMotion(SafetyManager::STOPPED, 0);
            acknowledge(version, sessionId, sequence,
                        obstacleDetected ? "ERROR|OBSTACLE" : "ERROR|SENSOR_NOT_READY");
            if (obstacleDetected) Serial.println("EVENT|1|0|BLOCKED|OBSTACLE");
            return;
        }
        if (speed == 0) motors->stop();
        else if (forward) motors->setAll(speed);
        else if (reverse) motors->setAll(-speed);
        // Physical layout: M0/M1 are the left side; M2/M3 are the right side.
        // RIGHT uses the direction the user confirmed: left side reverse,
        // right side forward. LEFT is the inverse.
        else if (left) {
            motors->setMotor(0,speed); motors->setMotor(1,speed);
            motors->setMotor(2,-speed); motors->setMotor(3,-speed);
        } else {
            motors->setMotor(0,-speed); motors->setMotor(1,-speed);
            motors->setMotor(2,speed); motors->setMotor(3,speed);
        }
        safety->setActiveMotion(motion, (uint8_t)speed);
        acknowledge(version, sessionId, sequence, "OK"); return;
    }
    if (!strcmp(field[4], "EYES") && count == 6) {
        if (!strcmp(field[5],"IDLE")) eyes->setExpression(EXPR_IDLE);
        else if (!strcmp(field[5],"HAPPY")) eyes->setExpression(EXPR_HAPPY);
        else if (!strcmp(field[5],"THINKING") || !strcmp(field[5],"LISTENING")) eyes->setExpression(EXPR_CURIOUS);
        else if (!strcmp(field[5],"SPEAKING")) eyes->setExpression(EXPR_HAPPY);
        else if (!strcmp(field[5],"ALERT")) eyes->setExpression(EXPR_ANGRY);
        else if (!strcmp(field[5],"SLEEP")) eyes->setExpression(EXPR_SLEEPY);
        else { acknowledge(version, sessionId, sequence, "ERROR|INVALID_ARGUMENT"); return; }
        safety->notePiFrame();
        acknowledge(version, sessionId, sequence, "OK"); return;
    }
    if (!strcmp(field[4], "SERVO") && count == 9 && !strcmp(field[5],"MOVE")) {
        long pan, tilt, duration;
        if (!parseLong(field[6], pan) || !parseLong(field[7], tilt) ||
            !parseLong(field[8], duration) || pan < 0 || pan > 180 ||
            tilt < 0 || tilt > 180 || duration < 50 || duration > 2000) {
            acknowledge(version, sessionId, sequence, "ERROR|OUT_OF_RANGE"); return;
        }
        safety->notePiFrame();
        servos->moveTo((float)pan, (float)tilt, (unsigned long)duration);
        acknowledge(version, sessionId, sequence, "OK"); return;
    }
    if (!strcmp(field[4], "SERVO") && count == 8 && !strcmp(field[5],"PAN_TILT")) {
        long pan, tilt;
        if (!parseLong(field[6], pan)) { acknowledge(version, sessionId, sequence, "ERROR|INVALID_ARGUMENT"); return; }
        if (!parseLong(field[7], tilt) || pan < 0 || pan > 180 || tilt < 0 || tilt > 180) {
            acknowledge(version, sessionId, sequence, "ERROR|OUT_OF_RANGE"); return;
        }
        safety->notePiFrame(); servos->track(pan, tilt);
        acknowledge(version, sessionId, sequence, "OK"); return;
    }
    if (!strcmp(field[4], "ENCODERS") && count == 5) {
        Serial.print("ENC|"); Serial.print(PROTOCOL_VERSION); Serial.print('|');
        Serial.print(sessionId); Serial.print('|'); Serial.print(sequence);
        for (uint8_t encoderId = 0; encoderId < 4; ++encoderId) {
            Serial.print('|'); Serial.print(motors->encoderCount(encoderId));
        }
        Serial.println(); safety->notePiFrame(); return;
    }
    acknowledge(version, sessionId, sequence, "ERROR|INVALID_COMMAND");
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
    Serial.print("TEL|"); Serial.print(PROTOCOL_VERSION); Serial.print("|0|SENSORS");
    const ToFManager::SensorId ids[] = {ToFManager::FRONT_LEFT, ToFManager::FRONT_CENTER, ToFManager::FRONT_RIGHT};
    const char* labels[] = {"|TOF_L|", "|TOF_C|", "|TOF_R|"};
    for (uint8_t i = 0; i < 3; ++i) {
        Serial.print(labels[i]);
        if (!tof->isFresh(ids[i])) Serial.print("NA");
        else if (tof->isValid(ids[i])) Serial.print(tof->getDistanceMm(ids[i]));
        else if (tof->isOutOfRange(ids[i])) Serial.print("FAR");
        else Serial.print("NA");
    }
    Serial.print("|US_REAR|");
    if (!rear->isFresh()) Serial.print("NA");
    else if (rear->isValid()) Serial.print((long)(rear->getDistanceCm() * 10.0f));
    else if (rear->isOutOfRange()) Serial.print("FAR");
    else Serial.print("NA");
    Serial.println();
}

void CommunicationManager::update() {
    readCommands();
    if (safety && safety->consumeObstacleStop()) {
        Serial.println("EVENT|1|0|STOP|OBSTACLE");
    }
    sendTelemetry();
}
