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
    this.leaseId,
  });

  final String commandId;
  final String? requestId;
  final String command;
  final String status;
  final String controlMode;
  final String? errorCode;
  final String? timestamp;
  final String? leaseId;

  factory RobotCommandResult.fromJson(Map<String, dynamic> json) {
    final commandId = _requiredString(json, 'command_id');
    final command = _requiredString(json, 'command');
    final rawLeaseId = json['lease_id'];
    if (rawLeaseId != null && rawLeaseId is! String) {
      throw const FormatException('Expected "lease_id" to be a string or null.');
    }
    return RobotCommandResult(
      commandId: commandId,
      requestId: _optionalString(json, 'request_id'),
      command: command,
      status: _requiredString(json, 'status'),
      controlMode: _requiredString(json, 'control_mode'),
      errorCode: _optionalString(json, 'error_code'),
      timestamp: _optionalString(json, 'timestamp'),
      leaseId: rawLeaseId as String? ?? (command == 'stop' ? null : commandId),
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
