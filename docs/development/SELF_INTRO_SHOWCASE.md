# Thashu self-introduction showcase

There is no separate competition mode. Ask Thashu **tell me about yourself**,
**introduce yourself**, **what can you do**, or another supported introduction
phrase to start one spoken feature tour.

The response covers the Pi/ESP32 split, voice and local reasoning, expressive
eyes, head servos, camera face and upper-body tracking, consent-based saved-face
recognition, distance sensors, follow, phone-app control, and idle power saving.
Between spoken parts, the camera briefly resumes and the head tracks one clear
face or upper-body target. If current recognition confirms an enrolled person,
Thashu may name them; otherwise it says no confirmed identity is available.

The tour then attempts one short, low-speed step in each direction: forward,
backward, left, and right. Each movement goes through `RobotCommandManager`,
which requires fresh readings and enforces the current obstacle clearance. The
Pi starts a 350 ms movement timer; the ESP32 must acknowledge the move and the
normal STOP. The Pi restores the previous manual/auto selection with another
acknowledged STOP. If the controller, mode switch, sensor check, move, or stop
acknowledgement fails, the tour stops moving and reports that failure. Follow
is not started automatically; it remains an explicit `follow me` request.

This is code behavior, not a verified physical-motion result. Before using it
in a competition, install the current `main` commit and rehearse on a clear,
supervised floor with the robot restrained as appropriate. Confirm the move
and STOP acknowledgements, sensor freshness, turn direction, physical travel,
and restoration of the selected control mode. The 350 ms duration and PWM 105
are command parameters, not a measured travel distance or stopping distance.
