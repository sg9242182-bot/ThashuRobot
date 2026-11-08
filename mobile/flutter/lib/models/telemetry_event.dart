import 'dart:convert';

/// A parsed message from Vishal's currently documented telemetry socket.
sealed class TelemetryEvent {
  const TelemetryEvent();
}

final class CommandResultEvent extends TelemetryEvent {
  const CommandResultEvent({
    required this.commandId,
    required this.status,
    required this.timestamp,
    this.requestId,
    this.errorCode,
  });

  final String commandId;
  final String status;
  final String timestamp;
  final String? requestId;
  final String? errorCode;
}

final class Esp32LineEvent extends TelemetryEvent {
  const Esp32LineEvent({
    required this.line,
    required this.receivedAt,
    this.sensorFrame,
    this.sensorParseError,
  });

  final String line;
  final DateTime receivedAt;
  final SensorTelemetryFrame? sensorFrame;
  final String? sensorParseError;
}

enum SensorReadingKind { distance, far, unavailable }

final class SensorReading {
  const SensorReading._({
    required this.rawValue,
    required this.kind,
    this.distanceMm,
  });

  final String rawValue;
  final SensorReadingKind kind;
  final int? distanceMm;

  String get displayValue => switch (kind) {
    SensorReadingKind.distance => '$distanceMm mm',
    SensorReadingKind.far => 'FAR',
    SensorReadingKind.unavailable => 'NA',
  };

  static SensorReading? parse(String value) {
    if (value == 'FAR') {
      return const SensorReading._(
        rawValue: 'FAR',
        kind: SensorReadingKind.far,
      );
    }
    if (value == 'NA') {
      return const SensorReading._(
        rawValue: 'NA',
        kind: SensorReadingKind.unavailable,
      );
    }
    final distance = int.tryParse(value);
    if (distance == null || distance < 0) return null;
    return SensorReading._(
      rawValue: value,
      kind: SensorReadingKind.distance,
      distanceMm: distance,
    );
  }
}

final class SensorTelemetryFrame {
  const SensorTelemetryFrame({
    required this.sequence,
    required this.tofLeft,
    required this.tofCenter,
    required this.tofRight,
    required this.ultrasonicRear,
  });

  final int sequence;
  final SensorReading tofLeft;
  final SensorReading tofCenter;
  final SensorReading tofRight;
  final SensorReading ultrasonicRear;

  static SensorTelemetryFrame? parse(String line) {
    final fields = line.split('|');
    if (fields.length != 11 || fields[0] != 'TEL' || fields[2] != 'SENSORS') {
      return null;
    }
    final sequence = int.tryParse(fields[1]);
    if (sequence == null || sequence < 0) return null;

    final values = <String, String>{};
    for (var index = 3; index < fields.length; index += 2) {
      final key = fields[index];
      if (values.containsKey(key)) return null;
      values[key] = fields[index + 1];
    }
    if (values.length != 4 ||
        !values.containsKey('TOF_L') ||
        !values.containsKey('TOF_C') ||
        !values.containsKey('TOF_R') ||
        !values.containsKey('US_REAR')) {
      return null;
    }

    final tofLeft = SensorReading.parse(values['TOF_L']!);
    final tofCenter = SensorReading.parse(values['TOF_C']!);
    final tofRight = SensorReading.parse(values['TOF_R']!);
    final ultrasonicRear = SensorReading.parse(values['US_REAR']!);
    if (tofLeft == null ||
        tofCenter == null ||
        tofRight == null ||
        ultrasonicRear == null) {
      return null;
    }

    return SensorTelemetryFrame(
      sequence: sequence,
      tofLeft: tofLeft,
      tofCenter: tofCenter,
      tofRight: tofRight,
      ultrasonicRear: ultrasonicRear,
    );
  }
}

final class UnknownTelemetryEvent extends TelemetryEvent {
  const UnknownTelemetryEvent(this.type);

  final String type;
}

final class MalformedTelemetryEvent extends TelemetryEvent {
  const MalformedTelemetryEvent(this.reason);

  final String reason;
}

/// Parses a WebSocket frame without throwing for malformed or unknown input.
TelemetryEvent parseTelemetryEvent(Object? frame) {
  try {
    final String source;
    if (frame is String) {
      source = frame;
    } else if (frame is List<int>) {
      source = utf8.decode(frame);
    } else {
      return const MalformedTelemetryEvent('Unsupported frame data.');
    }

    final decoded = jsonDecode(source);
    if (decoded is! Map<String, dynamic>) {
      return const MalformedTelemetryEvent('Expected a JSON object.');
    }

    final type = decoded['type'];
    if (type is! String || type.isEmpty) {
      return const MalformedTelemetryEvent('Missing string field "type".');
    }

    switch (type) {
      case 'command_result':
        return CommandResultEvent(
          commandId: _requiredString(decoded, 'command_id'),
          status: _requiredString(decoded, 'status'),
          timestamp: _requiredString(decoded, 'timestamp'),
          requestId: _optionalString(decoded, 'request_id'),
          errorCode: _optionalString(decoded, 'error_code'),
        );
      case 'esp32_line':
        final line = _requiredString(decoded, 'line');
        final receivedAt = _requiredUtcDateTime(decoded, 'received_at');
        if (line.startsWith('TEL|')) {
          final sensorFrame = SensorTelemetryFrame.parse(line);
          return Esp32LineEvent(
            line: line,
            receivedAt: receivedAt,
            sensorFrame: sensorFrame,
            sensorParseError: sensorFrame == null
                ? 'Invalid sensor TEL frame.'
                : null,
          );
        }
        return Esp32LineEvent(line: line, receivedAt: receivedAt);
      default:
        return UnknownTelemetryEvent(type);
    }
  } on FormatException catch (error) {
    return MalformedTelemetryEvent(error.message);
  }
}

DateTime _requiredUtcDateTime(Map<String, dynamic> json, String key) {
  final value = json[key];
  final parsed = value is String ? DateTime.tryParse(value) : null;
  if (parsed == null || !parsed.isUtc) {
    throw FormatException('Expected "$key" to be an ISO 8601 UTC timestamp.');
  }
  return parsed;
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String) {
    throw FormatException('Expected "$key" to be a string.');
  }
  return value;
}

String? _optionalString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value == null) return null;
  if (value is! String) {
    throw FormatException('Expected "$key" to be a string or null.');
  }
  return value;
}
