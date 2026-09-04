#include "servo_manager.h"
#include "command_parser.h"

ServoManager servoManager;
CommandParser commandParser;

void setup()
{
    Serial.begin(115200);

    delay(500);

    Serial.println();
    Serial.println("THASHU SERVO MODULE TEST");
    Serial.println("Initializing...");

    if (!servoManager.begin()) {

        Serial.println(
            "SERVO INITIALIZATION FAILED"
        );

        while (true) {
            delay(1000);
        }
    }

    commandParser.begin(&servoManager);

    Serial.println("SERVOS READY");

    Serial.println(
        "Commands:"
    );

    Serial.println(
        "MOVE <pan> <tilt> <duration>"
    );

    Serial.println(
        "TRACK <pan> <tilt>"
    );

    Serial.println("CENTER");
    Serial.println("STOP");
}

void loop()
{
    // Servo control gets serviced continuously.
    servoManager.update();

    // Serial parser is completely non-blocking.
    commandParser.update();
}