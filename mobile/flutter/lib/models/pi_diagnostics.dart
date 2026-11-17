class PiDiagnosticsSnapshot {
  const PiDiagnosticsSnapshot({
    required this.observedAt,
    required this.checks,
  });

  final DateTime observedAt;
  final List<PiDiagnosticCheck> checks;

  factory PiDiagnosticsSnapshot.fromJson(Map<String, dynamic> json) {
    final observedAt = _parseTimestamp(json['observed_at'], 'observed_at');
    final rawChecks = json['checks'];
    if (rawChecks is! List) {
      throw const FormatException('Expected "checks" to be an array.');
    }
    return PiDiagnosticsSnapshot(
      observedAt: observedAt,
      checks: List.unmodifiable(
        rawChecks.map((value) {
          if (value is! Map<String, dynamic>) {
            throw const FormatException('Expected each diagnostic check to be an object.');
          }
          return PiDiagnosticCheck.fromJson(value);
        }),
      ),
    );
  }
}

class PiDiagnosticCheck {
  const PiDiagnosticCheck({
    required this.name,
    required this.status,
    required this.observedAt,
    required this.source,
    required this.reasonCode,
    this.ageMs,
  });

  static const names = {
    'api_liveness',
    'esp32_transport',
    'sensor_telemetry',
    'controller_readiness',
  };
  static const statuses = {'PASS', 'WARNING', 'FAIL', 'UNKNOWN'};

  final String name;
  final String status;
  final DateTime observedAt;
  final String source;
  final String reasonCode;
  final int? ageMs;

  factory PiDiagnosticCheck.fromJson(Map<String, dynamic> json) {
    final name = _requiredString(json, 'name');
    final status = _requiredString(json, 'status');
    final age = json['age_ms'];
    if (!names.contains(name)) {
      throw FormatException('Unsupported diagnostic check name: $name.');
    }
    if (!statuses.contains(status)) {
      throw FormatException('Unsupported diagnostic status: $status.');
    }
    if (name == 'sensor_telemetry') {
      if (!json.containsKey('age_ms')) {
        throw const FormatException('"age_ms" is required for sensor_telemetry.');
      }
      if (age != null && (age is! int || age < 0)) {
        throw const FormatException('"age_ms" must be a nonnegative integer or null.');
      }
    } else if (json.containsKey('age_ms')) {
      throw const FormatException('"age_ms" is only valid for sensor_telemetry.');
    }

    return PiDiagnosticCheck(
      name: name,
      status: status,
      observedAt: _parseTimestamp(json['observed_at'], 'observed_at'),
      source: _requiredString(json, 'source'),
      reasonCode: _requiredString(json, 'reason_code'),
      ageMs: age as int?,
    );
  }
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.isEmpty) {
    throw FormatException('Expected "$key" to be a non-empty string.');
  }
  return value;
}

DateTime _parseTimestamp(Object? value, String field) {
  if (value is! String) {
    throw FormatException('Expected "$field" to be a timestamp string.');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null || !parsed.isUtc) {
    throw FormatException('Expected "$field" to be a UTC timestamp.');
  }
  return parsed;
}
