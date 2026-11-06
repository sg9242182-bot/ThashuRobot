/// Client-side checks for confirmed movement inputs.
///
/// Sensor freshness remains Pi-authoritative because the current status
/// response does not expose sensor readings or their age.
enum RobotMoveValidationError {
  manualModeRequired,
  unsupportedDirection,
  speedOutOfRange,
}

class RobotMoveValidator {
  RobotMoveValidator._();

  static const Set<String> directions = {
    'forward',
    'backward',
    'left',
    'right',
  };

  static RobotMoveValidationError? validate({
    required String controlMode,
    required String direction,
    required int speed,
  }) {
    if (controlMode != 'MANUAL') {
      return RobotMoveValidationError.manualModeRequired;
    }
    if (!directions.contains(direction)) {
      return RobotMoveValidationError.unsupportedDirection;
    }
    if (speed < 0 || speed > 255) {
      return RobotMoveValidationError.speedOutOfRange;
    }
    return null;
  }
}
