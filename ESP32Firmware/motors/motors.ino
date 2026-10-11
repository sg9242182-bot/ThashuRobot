#include "motor_manager.h"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

MotorManager motors;
ToFManager frontTof;

namespace {
constexpr size_t COMMAND_BUFFER_SIZE = 128;
char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;
bool discardingCommand = false;

void acknowledge(long sequence, const char* result) {
    Serial.print("ACK|");
    Serial.print(sequence);
    Serial.print('|');
    Serial.println(result);
}

bool frontSafe() {
    const ToFManager::SensorId sensors[] = {
        ToFManager::FRONT_LEFT,
        ToFManager::FRONT_CENTER,
        ToFManager::FRONT_RIGHT,
    };
    for (uint8_t i = 0; i < ToFManager::SENSOR_COUNT; ++i) {
        if (!frontTof.isFresh(sensors[i]) || !frontTof.isValid(sensors[i]) ||
            frontTof.isObstacleDetected(sensors[i])) {
            return false;
        }
    }
    return true;
}

bool parseSpeed(const char* text, int16_t& speed) {
    if (text == nullptr || *text == '\0') {
        return false;
    }
    char* end = nullptr;
    const long parsed = strtol(text, &end, 10);
    if (*end != '\0' || parsed < 0 || parsed > 255) {
        return false;
    }
    speed = static_cast<int16_t>(parsed);
    return true;
}

void handleCommand(char* line) {
    char* save = nullptr;
    char* field[6] = {};
    uint8_t count = 0;
    for (char* token = strtok_r(line, "|", &save);
         token != nullptr && count < 6;
         token = strtok_r(nullptr, "|", &save)) {
        field[count++] = token;
    }

    if (count < 3 || strcmp(field[0], "CMD") != 0) {
        return;
    }
    char* sequenceEnd = nullptr;
    const long sequence = strtol(field[1], &sequenceEnd, 10);
    if (*field[1] == '\0' || *sequenceEnd != '\0' || sequence < 0) {
        return;
    }

    const bool isStop = strcmp(field[2], "STOP") == 0;
    const bool isHeartbeat = strcmp(field[2], "HEARTBEAT") == 0;
    if (strcmp(field[2], "ENCODERS") == 0 && count == 3) {
        Serial.print("ENC|");
        Serial.print(sequence);
        for (uint8_t motor = 0; motor < 4; ++motor) {
            Serial.print('|');
            Serial.print(motors.encoderCount(motor));
        }
        Serial.println();
        return;
    }
    if (isStop) {
        // Service STOP immediately and disable both bridges in hardware.
        motors.notePiMessage();
        motors.stop();
        acknowledge(sequence, "OK");
        return;
    }
    if (isHeartbeat && count == 3) {
        motors.notePiMessage();
        Serial.print("ACK|");
        Serial.print(sequence);
        Serial.println("|ALIVE");
        return;
    }

    if (strcmp(field[2], "MOTOR") != 0 || count != 5) {
        acknowledge(sequence, "ERROR|INVALID_COMMAND");
        return;
    }

    int16_t speed = 0;
    if (!parseSpeed(field[4], speed)) {
        acknowledge(sequence, "ERROR|OUT_OF_RANGE");
        return;
    }
    motors.notePiMessage();

    const bool isForward = strcmp(field[3], "FORWARD") == 0;
    const bool isTurn = strcmp(field[3], "LEFT") == 0 ||
        strcmp(field[3], "RIGHT") == 0;
    if ((isForward || isTurn) && !frontSafe()) {
        motors.stop();
        acknowledge(sequence, "ERROR|SAFETY_STOP");
        return;
    }

    if (isForward) {
        motors.setAll(speed);
    } else if (strcmp(field[3], "BACKWARD") == 0) {
        motors.setAll(-speed);
    } else if (strcmp(field[3], "LEFT") == 0) {
        // Motor indexes follow the frozen pin order. This differential-turn
        // mapping assumes channels 1/2/3/4 are left/right/left/right wheels.
        motors.setMotor(0, -speed);
        motors.setMotor(1, speed);
        motors.setMotor(2, -speed);
        motors.setMotor(3, speed);
    } else if (strcmp(field[3], "RIGHT") == 0) {
        motors.setMotor(0, speed);
        motors.setMotor(1, -speed);
        motors.setMotor(2, speed);
        motors.setMotor(3, -speed);
    } else {
        acknowledge(sequence, "ERROR|INVALID_ARGUMENT");
        return;
    }

    if (motors.isFaulted()) {
        acknowledge(sequence, "ERROR|HARDWARE_FAULT");
    } else {
        acknowledge(sequence, "OK");
    }
}

void readCommands() {
    size_t bytesRead = 0;
    while (Serial.available() > 0 && bytesRead < COMMAND_BUFFER_SIZE) {
        ++bytesRead;
        const char ch = static_cast<char>(Serial.read());
        if (ch == '\n') {
            if (!discardingCommand && commandLength > 0) {
                commandBuffer[commandLength] = '\0';
                if (commandLength > 0 && commandBuffer[commandLength - 1] == '\r') {
                    commandBuffer[commandLength - 1] = '\0';
                }
                handleCommand(commandBuffer);
            }
            commandLength = 0;
            discardingCommand = false;
        } else if (!discardingCommand) {
            if (commandLength + 1 >= COMMAND_BUFFER_SIZE) {
                commandLength = 0;
                discardingCommand = true;
            } else {
                commandBuffer[commandLength++] = ch;
            }
        }
    }
}
}

void setup() {
    Serial.begin(115200);
    if (!motors.begin(frontTof)) {
        Serial.println("FAULT|0|SENSOR|TOF_INIT");
        while (true) {
            motors.stop();
            delay(100);
        }
    }
    Serial.println("EVENT|0|READY");
}

void loop() {
    motors.update();
    readCommands();
}
