#pragma once

#include <stdint.h>

class MotorManager {
public:
    bool begin();

    void update();

    // Speed: -255 to +255
    // Positive = forward
    // Negative = reverse
    // Zero = stop
    void setMotor(uint8_t motor, int16_t speed);

    void setAll(int16_t speed);

    void stop();

    bool isFaulted() const;
};