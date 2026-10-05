#pragma once

#include "../motors/motor_manager.h"
#include "../safetymanager/safety_manager.h"
#include "../eyes/eye_manager.h"
#include "../servomanager/servo_manager.h"

// Owns the USB serial protocol and routes Pi requests to hardware/safety managers.
class CommunicationManager {
public:
    void begin(MotorManager& motors, SafetyManager& safety, EyeManager& eyes, ServoManager& servos);
    void update();
    void reportFault(const char* subsystem, const char* detail);

private:
    static constexpr size_t COMMAND_BUFFER_SIZE = 128;
    MotorManager* motors = nullptr;
    SafetyManager* safety = nullptr;
    EyeManager* eyes = nullptr;
    ServoManager* servos = nullptr;
    char commandBuffer[COMMAND_BUFFER_SIZE] = {};
    size_t commandLength = 0;
    bool discardingCommand = false;
    unsigned long lastTelemetryMs = 0;
    void handle(char* line);
    void readCommands();
    void sendTelemetry();
    void acknowledge(long sequence, const char* result);
};
