/// Fields currently returned by the Pi's GET /api/v1/status endpoint.
///
/// Values remain strings because the backend has not yet published enums for
/// readiness or transport state. This avoids inventing allowed values in the
/// Flutter client.
class PiStatus {
  const PiStatus({
    required this.api,
    required this.esp32Transport,
    required this.controlMode,
    required this.controllerReadiness,
  });

  final String api;
  final String esp32Transport;
  final String controlMode;
  final String controllerReadiness;

  factory PiStatus.fromJson(Map<String, dynamic> json) {
    return PiStatus(
      api: _requiredString(json, 'api'),
      esp32Transport: _requiredString(json, 'esp32_transport'),
      controlMode: _requiredString(json, 'control_mode'),
      controllerReadiness: _requiredString(json, 'controller_readiness'),
    );
  }

  static String _requiredString(Map<String, dynamic> json, String key) {
    final value = json[key];
    if (value is! String) {
      throw FormatException('Expected "$key" to be a string.');
    }
    return value;
  }
}
