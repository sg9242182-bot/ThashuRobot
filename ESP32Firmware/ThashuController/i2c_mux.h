#pragma once

#include <Arduino.h>
#include <Wire.h>

// TCA9548A-compatible 8-channel mux used by all six ToF sensors and both
// same-address OLEDs. Callers run sequentially from the main loop.
constexpr uint8_t I2C_MUX_ADDRESS = 0x70;
constexpr uint8_t I2C_SDA_PIN = 21;
constexpr uint8_t I2C_SCL_PIN = 22;

inline bool selectI2cMuxChannels(uint8_t channelMask) {
    if (channelMask == 0) return false;
    Wire.beginTransmission(I2C_MUX_ADDRESS);
    Wire.write(channelMask);
    return Wire.endTransmission() == 0;
}

inline bool selectI2cMuxChannel(uint8_t channel) {
    if (channel > 7) return false;
    return selectI2cMuxChannels(static_cast<uint8_t>(1U << channel));
}

inline bool deselectI2cMux() {
    Wire.beginTransmission(I2C_MUX_ADDRESS);
    Wire.write(static_cast<uint8_t>(0));
    return Wire.endTransmission() == 0;
}
