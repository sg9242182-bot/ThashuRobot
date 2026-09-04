#pragma once

class ServoManager {
public:
    bool begin();

    void update();

    void moveTo(float pan, float tilt, unsigned long durationMs);

    void track(float pan, float tilt);

    void center();

    void stop();

    bool isMoving() const;

    float getPanAngle() const;

    float getTiltAngle() const;
};