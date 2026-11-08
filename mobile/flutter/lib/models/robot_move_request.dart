import 'dart:math';

/// One logical move action. Reuse the same instance/requestId for retries.
class RobotMoveRequest {
  const RobotMoveRequest({
    required this.requestId,
    required this.direction,
    required this.speed,
  });

  final String requestId;
  final String direction;
  final int speed;

  Map<String, dynamic> toJson() => {
    'request_id': requestId,
    'direction': direction,
    'speed': speed,
  };
}

/// Generates UUID v4 request IDs for movement actions.
/// Keep the generated ID when retrying the same movement action.
abstract final class RobotRequestId {
  static final Random _secureRandom = Random.secure();
  static final RegExp _uuidPattern = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  static bool isValid(String value) => _uuidPattern.hasMatch(value);

  static String generate() {
    final bytes = List<int>.generate(16, (_) => _secureRandom.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes
        .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }
}
