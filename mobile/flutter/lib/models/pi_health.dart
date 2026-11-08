/// Liveness response from the Pi's unauthenticated GET /health endpoint.
class PiHealth {
  const PiHealth({required this.status});

  final String status;

  factory PiHealth.fromJson(Map<String, dynamic> json) {
    final value = json['status'];
    if (value is! String) {
      throw const FormatException('Expected "status" to be a string.');
    }
    return PiHealth(status: value);
  }
}
