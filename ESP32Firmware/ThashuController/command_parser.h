#pragma once

#include <stddef.h>

class ServoManager;

class CommandParser {
public:
    void begin(ServoManager* servoManager);

    void update();

private:
    static constexpr size_t BUFFER_SIZE = 96;

    char buffer[BUFFER_SIZE];
    size_t bufferIndex = 0;

    ServoManager* servo = nullptr;

    void processCommand(const char* command);
};