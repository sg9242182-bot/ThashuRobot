#include "command_parser.h"
#include "servo_manager.h"

#include <Arduino.h>
#include <stdio.h>
#include <string.h>

void CommandParser::begin(
    ServoManager* servoManager
)
{
    servo = servoManager;

    bufferIndex = 0;
    buffer[0] = '\0';
}

void CommandParser::update()
{
    while (Serial.available() > 0) {

        char c = Serial.read();

        // ----------------------------------------------------
        // End of command
        // ----------------------------------------------------

        if (c == '\n' || c == '\r') {

            if (bufferIndex > 0) {

                buffer[bufferIndex] = '\0';

                processCommand(buffer);

                bufferIndex = 0;
                buffer[0] = '\0';
            }

            continue;
        }

        // ----------------------------------------------------
        // Store character
        // ----------------------------------------------------

        if (bufferIndex < BUFFER_SIZE - 1) {

            buffer[bufferIndex++] = c;

        } else {

            // Buffer overflow.
            // Discard the current command safely.

            bufferIndex = 0;
            buffer[0] = '\0';

            Serial.println("ERR COMMAND TOO LONG");
        }
    }
}

// ============================================================
// COMMAND PROCESSING
// ============================================================

void CommandParser::processCommand(
    const char* command
)
{
    if (servo == nullptr) {
        return;
    }

    // --------------------------------------------------------
    // MOVE
    // --------------------------------------------------------

    float pan;
    float tilt;
    unsigned long duration;

    if (sscanf(
            command,
            "MOVE %f %f %lu",
            &pan,
            &tilt,
            &duration
        ) == 3) {

        if (duration < 100) {
            duration = 100;
        }

        servo->moveTo(
            pan,
            tilt,
            duration
        );

        Serial.println("OK MOVE");

        return;
    }

    // --------------------------------------------------------
    // TRACK
    // --------------------------------------------------------

    if (sscanf(
            command,
            "TRACK %f %f",
            &pan,
            &tilt
        ) == 2) {

        servo->track(
            pan,
            tilt
        );

        Serial.println("OK TRACK");

        return;
    }

    // --------------------------------------------------------
    // CENTER
    // --------------------------------------------------------

    if (
        strcasecmp(command, "CENTER") == 0
    ) {

        servo->center();

        Serial.println("OK CENTER");

        return;
    }

    // --------------------------------------------------------
    // STOP
    // --------------------------------------------------------

    if (
        strcasecmp(command, "STOP") == 0
    ) {

        servo->stop();

        Serial.println("OK STOP");

        return;
    }

    // --------------------------------------------------------
    // Unknown command
    // --------------------------------------------------------

    Serial.println("ERR UNKNOWN COMMAND");
}