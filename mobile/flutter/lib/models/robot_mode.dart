/// The two mode values accepted by POST /api/v1/robot/mode.
enum RobotMode {
  manual('MANUAL'),
  automatic('AUTO');

  const RobotMode(this.apiValue);

  final String apiValue;

  Map<String, dynamic> toRequestJson() => {'mode': apiValue};
}

class RobotModeResponse {
  const RobotModeResponse({required this.mode, required this.status});

  final String mode;
  final String status;

  factory RobotModeResponse.fromJson(Map<String, dynamic> json) {
    final mode = json['mode'];
    final status = json['status'];
    if (mode is! String || status is! String) {
      throw const FormatException(
        'Expected mode and status strings in the mode response.',
      );
    }
    return RobotModeResponse(mode: mode, status: status);
  }
}
