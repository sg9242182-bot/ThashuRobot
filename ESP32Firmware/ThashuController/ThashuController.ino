#include "../motors/motor_manager.h"
#include "../sensors/ultrasonic_manager/ultrasonic_manager.h"
#include "../eyes/eye_manager.h"
#include "../servomanager/servo_manager.h"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

MotorManager motors;
ToFManager frontTof;
UltrasonicManager rearUltrasonic;
EyeManager eyes;
ServoManager servos;

namespace {
constexpr size_t COMMAND_BUFFER_SIZE = 128;
char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;
bool discardingCommand = false;
bool reversing = false;
unsigned long lastTelemetryMs = 0;

void ack(long seq, const char *result) {
  Serial.print("ACK|"); Serial.print(seq); Serial.print('|'); Serial.println(result);
}
bool number(const char *text, long &value) {
  if (!text || !*text) return false;
  char *end = nullptr;
  value = strtol(text, &end, 10);
  return *end == '\0';
}
bool frontSafe() {
  const ToFManager::SensorId ids[] = {ToFManager::FRONT_LEFT, ToFManager::FRONT_CENTER, ToFManager::FRONT_RIGHT};
  for (uint8_t i = 0; i < 3; ++i) {
    if (!frontTof.isFresh(ids[i]) || !frontTof.isValid(ids[i]) || frontTof.isObstacleDetected(ids[i])) return false;
  }
  return true;
}
void telemetry() {
  const unsigned long now = millis();
  if (now - lastTelemetryMs < 50) return;
  lastTelemetryMs = now;
  Serial.print("TEL|0|SENSORS");
  const ToFManager::SensorId ids[] = {ToFManager::FRONT_LEFT, ToFManager::FRONT_CENTER, ToFManager::FRONT_RIGHT};
  const char *keys[] = {"|TOF_L|", "|TOF_C|", "|TOF_R|"};
  for (uint8_t i = 0; i < 3; ++i) {
    Serial.print(keys[i]);
    if (frontTof.isFresh(ids[i]) && frontTof.isValid(ids[i])) Serial.print(frontTof.getDistanceMm(ids[i]));
    else Serial.print("NA");
  }
  Serial.print("|US_REAR|");
  if (rearUltrasonic.isValid()) Serial.print((long)(rearUltrasonic.getDistanceCm() * 10.0f));
  else Serial.print("NA");
  Serial.println();
}
void handle(char *line) {
  char *save = nullptr;
  char *f[7] = {};
  uint8_t n = 0;
  for (char *p = strtok_r(line, "|", &save); p && n < 7; p = strtok_r(nullptr, "|", &save)) f[n++] = p;
  if (n < 3 || strcmp(f[0], "CMD")) return;
  long seq;
  if (!number(f[1], seq) || seq < 0) return;

  if (!strcmp(f[2], "STOP") && n == 3) {
    motors.notePiMessage(); motors.stop(); reversing = false; ack(seq, "OK"); return;
  }
  if (!strcmp(f[2], "HEARTBEAT") && n == 3) {
    motors.notePiMessage(); ack(seq, "ALIVE"); return;
  }
  if (!strcmp(f[2], "MOTOR") && n == 5) {
    long speed;
    if (!number(f[4], speed) || speed < 0 || speed > 255) { ack(seq, "ERROR|OUT_OF_RANGE"); return; }
    const bool forward = !strcmp(f[3], "FORWARD");
    const bool backward = !strcmp(f[3], "BACKWARD");
    const bool left = !strcmp(f[3], "LEFT");
    const bool right = !strcmp(f[3], "RIGHT");
    if (!forward && !backward && !left && !right) { ack(seq, "ERROR|INVALID_ARGUMENT"); return; }
    motors.notePiMessage();
    const bool turning = left || right;
    if (speed > 0 && (forward || turning) && !frontSafe()) {
      motors.stop(); reversing = false; ack(seq, "ERROR|SAFETY_STOP"); return;
    }
    if (speed > 0 && (backward || turning) &&
        (!rearUltrasonic.isValid() || rearUltrasonic.isObstacleDetected())) {
      motors.stop(); reversing = false; ack(seq, "ERROR|SAFETY_STOP"); return;
    }
    if (forward) { motors.setAll(speed); reversing = false; }
    else if (backward) { motors.setAll(-speed); reversing = speed > 0; }
    else if (left) { motors.setMotor(0,-speed); motors.setMotor(1,speed); motors.setMotor(2,-speed); motors.setMotor(3,speed); reversing = speed > 0; }
    else { motors.setMotor(0,speed); motors.setMotor(1,-speed); motors.setMotor(2,speed); motors.setMotor(3,-speed); reversing = speed > 0; }
    ack(seq, motors.isFaulted() ? "ERROR|HARDWARE_FAULT" : "OK"); return;
  }
  if (!strcmp(f[2], "EYES") && n == 4) {
    if (!strcmp(f[3],"IDLE")) eyes.setExpression(EXPR_IDLE);
    else if (!strcmp(f[3],"HAPPY") || !strcmp(f[3],"SPEAKING")) eyes.setExpression(EXPR_HAPPY);
    else if (!strcmp(f[3],"THINKING") || !strcmp(f[3],"LISTENING")) eyes.setExpression(EXPR_CURIOUS);
    else if (!strcmp(f[3],"ALERT")) eyes.setExpression(EXPR_ANGRY);
    else if (!strcmp(f[3],"SLEEP")) eyes.setExpression(EXPR_SLEEPY);
    else { ack(seq,"ERROR|INVALID_ARGUMENT"); return; }
    motors.notePiMessage(); ack(seq,"OK"); return;
  }
  if (!strcmp(f[2], "SERVO") && n == 6 && !strcmp(f[3],"PAN_TILT")) {
    long pan, tilt;
    if (!number(f[4],pan) || !number(f[5],tilt) || pan < 0 || pan > 180 || tilt < 0 || tilt > 180) { ack(seq,"ERROR|OUT_OF_RANGE"); return; }
    servos.track(pan,tilt); motors.notePiMessage(); ack(seq,"OK"); return;
  }
  if (!strcmp(f[2], "ENCODERS") && n == 3) {
    Serial.print("ENC|"); Serial.print(seq);
    for (uint8_t i=0;i<4;i++) { Serial.print('|'); Serial.print(motors.encoderCount(i)); }
    Serial.println(); motors.notePiMessage(); return;
  }
  ack(seq,"ERROR|INVALID_COMMAND");
}
void readCommands() {
  size_t read = 0;
  while (Serial.available() && read++ < COMMAND_BUFFER_SIZE) {
    char c = (char)Serial.read();
    if (c == '\n') {
      if (!discardingCommand && commandLength) {
        commandBuffer[commandLength]='\0';
        if (commandLength && commandBuffer[commandLength-1]=='\r') commandBuffer[commandLength-1]='\0';
        handle(commandBuffer);
      }
      commandLength=0; discardingCommand=false;
    } else if (!discardingCommand) {
      if (commandLength+1 >= COMMAND_BUFFER_SIZE) { commandLength=0; discardingCommand=true; }
      else commandBuffer[commandLength++]=c;
    }
  }
}
}

void setup() {
  Serial.begin(115200);
  Serial.println("EVENT|0|BOOT");
  eyes.begin();
  if (!motors.begin(frontTof)) { Serial.println("FAULT|0|SENSOR|TOF_INIT"); while(true) { motors.stop(); delay(100); } }
  rearUltrasonic.begin();
  if (!servos.begin()) { Serial.println("FAULT|0|SERVO|INIT"); while(true) { motors.stop(); delay(100); } }
  eyes.setExpression(EXPR_IDLE);
  Serial.println("EVENT|0|READY");
}
void loop() {
  motors.update();
  rearUltrasonic.update();
  if (reversing && (!rearUltrasonic.isValid() || rearUltrasonic.isObstacleDetected())) {
    motors.stop(); reversing=false; Serial.println("EVENT|0|OBSTACLE");
  }
  servos.update();
  eyes.update();
  readCommands();
  telemetry();
}
