# Thashu competition showcase

Competition mode is a guided, voice-led demo. It does not start autonomous
motion when activated. Wake Thashu, then say **start competition mode**. Say
**next demo** to advance through each cue, **skip demo** to move to the next
cue, and **stop competition mode** to finish.

Each cue is staged so the operator can let judges see or try the feature:

1. **Expressions:** Thashu shows thinking, alert, happy, and idle eyes.
2. **Head servos:** the head looks left, right, and center; each move must get
   an ESP32 acknowledgement before the cue advances.
3. **Vision and identity:** the camera tracks people and announces a known
   saved identity only when it has a current confirmed match. Identity
   enrollment remains an explicit, separate voice flow.
4. **Wake word and voice:** invite a judge to ask a question or give a voice
   command.
5. **Personal memory:** explain that recall is available for a person whose
   face is recognized and whose memory was explicitly saved with confirmation.
6. **Follow:** invite one person to say **follow me**. Follow still requires a
   clear target, fresh camera/sensor data, and short safety-checked pulses.
7. **Distance sensors:** report the current front-left, front-center,
   front-right, and rear readings. Stale or missing readings are reported as
   unavailable and keep movement safety checks fail-closed.
8. **Roaming:** invite the operator to clear the test area and say **start
   roaming**. This remains opt-in, uses the existing low-speed sensor-gated
   pulses, and can be ended with the wake word or **stop roaming**.
9. **Phone app:** the operator can show the already-provisioned app's status,
   diagnostics, telemetry, and manual controls. Competition mode does not send
   app commands.
10. **Idle power save and touch wake:** explain the existing five-minute
    reduced-power and ten-minute software-sleep behavior; the presenter can
    demonstrate touch wake if the normal idle timer is allowed to expire.

Before the demo, charge the robot, confirm ESP32 readiness and fresh sensor
telemetry, provision the phone app, and use a clear, supervised area for follow
or roaming. Starting/advancing/exiting competition mode sends normal STOP and
requires its ESP32 acknowledgement. No reset or Emergency Stop route is added.
