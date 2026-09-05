#include "tof_manager.h"

ToFManager tof;

namespace {
constexpr unsigned long PRINT_INTERVAL_MS = 100;
unsigned long lastPrintTime = 0;
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("THASHU 3x VL53L0X TEST");

    if (!tof.begin()) {
        Serial.println("TOF_INIT_FAILED");
        while (true) {
            delay(1000);
        }
    }

    Serial.println("TOF_INIT_OK");
}

void loop() {
    // Keep sensor polling continuous and non-blocking.
    tof.update();

    // Limit serial output without blocking the sensor update loop.
    const unsigned long now = millis();
    if (now - lastPrintTime < PRINT_INTERVAL_MS) {
        return;
    }
    lastPrintTime = now;

    const ToFManager::SensorId sensors[] = {
        ToFManager::FRONT_LEFT,
        ToFManager::FRONT_CENTER,
        ToFManager::FRONT_RIGHT,
    };

    const char* names[] = {"LEFT", "CENTER", "RIGHT"};

    for (uint8_t i = 0; i < ToFManager::SENSOR_COUNT; ++i) {
        Serial.print(names[i]);
        Serial.print(": ");

        if (tof.hasReading(sensors[i])) {
            Serial.print(tof.getDistanceMm(sensors[i]));
            Serial.print(" mm");

            if (tof.isObstacleDetected(sensors[i])) {
                Serial.print(" [OBSTACLE]");
            }

            const uint8_t status = tof.getRangeStatus(sensors[i]);
            if (status != 0) {
                Serial.print(" [STATUS ");
                Serial.print(status);
                Serial.print("]");
            }
        } else {
            Serial.print("INVALID [OUT OF RANGE]");
        }

        if (i + 1 < ToFManager::SENSOR_COUNT) {
            Serial.print(" | ");
        }
    }

    Serial.println();
}
