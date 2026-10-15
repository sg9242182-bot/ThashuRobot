// Standalone bench sketch for ESP32Firmware/motors/MotorManagerIsolatedTest
// Includes the existing motor manager implementation from the parent folder.
// It intentionally has no ToF/SafetyManager dependency. Keep wheels lifted.
// Each nonzero command stops automatically after 1 second unless refreshed.

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

#include "../motor_manager.cpp"

MotorManager motors;

namespace {
constexpr size_t COMMAND_BUFFER_SIZE = 80;
constexpr int16_t TEST_SPEED_LIMIT = 80;
constexpr uint32_t COMMAND_RUN_MS = 1000;

char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;
bool discardingCommand = false;
bool driveActive = false;
uint32_t stopDeadline = 0;

void stopNow() {
    motors.stop();
    driveActive = false;
}

void acknowledge(long sequence, const char* result) {
    Serial.print("ACK|");
    Serial.print(sequence);
    Serial.print('|');
    Serial.println(result);
}

bool parseLong(const char* text, long& value) {
    if (!text || !*text) return false;
    char* end = nullptr;
    value = strtol(text, &end, 10);
    return end != text && *end == '\0';
}

void printEncoders(long sequence) {
    Serial.print("ENC|");
    Serial.print(sequence);
    for (uint8_t encoder = 0; encoder < 4; ++encoder) {
        Serial.print('|');
        Serial.print(motors.encoderCount(encoder));
    }
    Serial.println();
}

void handleCommand(char* line) {
    char* save = nullptr;
    char* fields[5] = {};
    uint8_t count = 0;
    for (char* token = strtok_r(line, "|", &save);
         token && count < 5;
         token = strtok_r(nullptr, "|", &save)) {
        fields[count++] = token;
    }

    long sequence = 0;
    if (count < 3 || strcmp(fields[0], "CMD") != 0 ||
        !parseLong(fields[1], sequence) || sequence < 0) {
        stopNow();
        Serial.println("ERROR|INVALID_COMMAND");
        return;
    }

    if (count == 3 && strcmp(fields[2], "STOP") == 0) {
        stopNow();
        acknowledge(sequence, "OK");
        return;
    }

    if (count == 3 && strcmp(fields[2], "ENCODERS") == 0) {
        printEncoders(sequence);
        return;
    }

    if (count != 5 || strcmp(fields[2], "MOTOR") != 0) {
        stopNow();
        acknowledge(sequence, "ERROR|INVALID_COMMAND");
        return;
    }

    long speed = 0;
    if (!parseLong(fields[4], speed) ||
        speed < -TEST_SPEED_LIMIT || speed > TEST_SPEED_LIMIT) {
        stopNow();
        acknowledge(sequence, "ERROR|OUT_OF_RANGE");
        return;
    }

    if (speed == 0) {
        stopNow();
        acknowledge(sequence, "OK");
        return;
    }

    if (strcmp(fields[3], "ALL") == 0) {
        motors.setAll(static_cast<int16_t>(speed));
    } else if (fields[3][0] == 'M' &&
               fields[3][1] >= '0' && fields[3][1] <= '3' &&
               fields[3][2] == '\0') {
        const uint8_t motor = static_cast<uint8_t>(fields[3][1] - '0');
        motors.setMotor(motor, static_cast<int16_t>(speed));
    } else {
        stopNow();
        acknowledge(sequence, "ERROR|INVALID_MOTOR");
        return;
    }

    driveActive = true;
    stopDeadline = millis() + COMMAND_RUN_MS;
    acknowledge(sequence, "OK");
}

void readCommands() {
    while (Serial.available() > 0) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\n') {
            if (!discardingCommand && commandLength > 0) {
                commandBuffer[commandLength] = '\0';
                if (commandLength > 0 &&
                    commandBuffer[commandLength - 1] == '\r') {
                    commandBuffer[commandLength - 1] = '\0';
                }
                handleCommand(commandBuffer);
            }
            commandLength = 0;
            discardingCommand = false;
        } else if (!discardingCommand) {
            if (commandLength + 1 >= COMMAND_BUFFER_SIZE) {
                stopNow();
                commandLength = 0;
                discardingCommand = true;
            } else {
                commandBuffer[commandLength++] = c;
            }
        }
    }
}
}  // namespace

void setup() {
    Serial.begin(115200);
    delay(200);

    if (!motors.begin()) {
        stopNow();
        Serial.println("FAULT|0|MOTOR|INIT");
        while (true) {
            motors.stop();
            delay(100);
        }
    }

    stopNow();
    Serial.println("EVENT|0|READY|ISOLATED_MOTOR_TEST");
    Serial.println("INFO|Commands: CMD|n|MOTOR|M0..M3 or ALL|signed_speed");
    Serial.println("INFO|Commands: CMD|n|STOP ; CMD|n|ENCODERS");
    Serial.println("INFO|Limit: +/-80 PWM for 1000 ms per command; repeat to continue");
}

void loop() {
    readCommands();

    if (driveActive &&
        static_cast<int32_t>(millis() - stopDeadline) >= 0) {
        stopNow();
        Serial.println("EVENT|0|STOP|COMMAND_TIMEOUT");
    }
}
