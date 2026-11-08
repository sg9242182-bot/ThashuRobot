import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/models/robot_move_validator.dart';

void main() {
  group('RobotMoveValidator', () {
    test('accepts each confirmed direction in Manual mode', () {
      for (final direction in RobotMoveValidator.directions) {
        expect(
          RobotMoveValidator.validate(
            controlMode: 'MANUAL',
            direction: direction,
            speed: 200,
          ),
          isNull,
        );
      }
    });

    test('rejects movement unless reported mode is Manual', () {
      expect(
        RobotMoveValidator.validate(
          controlMode: 'AUTO',
          direction: 'forward',
          speed: 200,
        ),
        RobotMoveValidationError.manualModeRequired,
      );
    });

    test('rejects directions outside the confirmed API values', () {
      expect(
        RobotMoveValidator.validate(
          controlMode: 'MANUAL',
          direction: 'stop',
          speed: 200,
        ),
        RobotMoveValidationError.unsupportedDirection,
      );
    });

    test('accepts the confirmed speed boundaries', () {
      for (final speed in [0, 255]) {
        expect(
          RobotMoveValidator.validate(
            controlMode: 'MANUAL',
            direction: 'forward',
            speed: speed,
          ),
          isNull,
        );
      }
    });

    test('rejects speeds outside 0 to 255', () {
      for (final speed in [-1, 256]) {
        expect(
          RobotMoveValidator.validate(
            controlMode: 'MANUAL',
            direction: 'forward',
            speed: speed,
          ),
          RobotMoveValidationError.speedOutOfRange,
        );
      }
    });
  });
}
