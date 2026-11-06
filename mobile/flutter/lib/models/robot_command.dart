/// Command fields returned by move, stop, and command-result endpoints.
class RobotCommandResult {
  const RobotCommandResult({
    required this.commandId,
    required this.command,
    required this.status,
    required this.controlMode,
    required this.errorCode,
    required this.timestamp,
    this.requestId,
  });

  final String commandId;
  final String? requestId;
  final String command;
  final String status;
  final String controlMode;
  final String? errorCode;
  final String? timestamp;

  factory RobotCommandResult.fromJson(Map<String, dynamic> json) {
    return RobotCommandResult(
      commandId: _requiredString(json, 'command_id'),
      requestId: _optionalString(json, 'request_id'),
      command: _requiredString(json, 'command'),
      status: _requiredString(json, 'status'),
      controlMode: _requiredString(json, 'control_mode'),
      errorCode: _optionalString(json, 'error_code'),
      timestamp: _optionalString(json, 'timestamp'),
    );
  }

  static String _requiredString(Map<String, dynamic> json, String key) {
    final value = json[key];
    if (value is! String) {
      throw FormatException('Expected "$key" to be a string.');
    }
    return value;
  }

  static String? _optionalString(Map<String, dynamic> json, String key) {
    final value = json[key];
    if (value == null) return null;
    if (value is! String) {
      throw FormatException('Expected "$key" to be a string or null.');
    }
    return value;
  }
}
