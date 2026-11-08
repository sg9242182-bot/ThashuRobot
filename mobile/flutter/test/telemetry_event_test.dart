import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/models/telemetry_event.dart';

void main() {
  test('parses the documented command_result event', () {
    final event = parseTelemetryEvent(
      '{"type":"command_result","command_id":"cmd-1",'
      '"request_id":"req-1","status":"acknowledged",'
      '"error_code":null,"timestamp":"2026-11-06T12:00:00Z"}',
    );

    expect(event, isA<CommandResultEvent>());
    final result = event as CommandResultEvent;
    expect(result.commandId, 'cmd-1');
    expect(result.requestId, 'req-1');
    expect(result.status, 'acknowledged');
    expect(result.errorCode, isNull);
    expect(result.timestamp, '2026-11-06T12:00:00Z');
  });

  test('parses an ESP32 line from text or UTF-8 frame data', () {
    const json =
        '{"type":"esp32_line","line":"READY",'
        '"received_at":"2026-11-07T12:00:00.123Z"}';

    expect(parseTelemetryEvent(json), isA<Esp32LineEvent>());
    expect(parseTelemetryEvent(utf8.encode(json)), isA<Esp32LineEvent>());
    expect((parseTelemetryEvent(json) as Esp32LineEvent).line, 'READY');
  });

  test('parses the documented sensor line, timestamp, FAR, and NA values', () {
    final event = parseTelemetryEvent(
      '{"type":"esp32_line",'
      '"line":"TEL|0|SENSORS|TOF_L|420|TOF_C|FAR|TOF_R|390|US_REAR|NA",'
      '"received_at":"2026-11-07T12:00:00.123Z"}',
    ) as Esp32LineEvent;

    expect(event.receivedAt, DateTime.utc(2026, 11, 7, 12, 0, 0, 123));
    expect(event.sensorParseError, isNull);
    expect(event.sensorFrame?.sequence, 0);
    expect(event.sensorFrame?.tofLeft.displayValue, '420 mm');
    expect(event.sensorFrame?.tofCenter.displayValue, 'FAR');
    expect(event.sensorFrame?.tofRight.displayValue, '390 mm');
    expect(event.sensorFrame?.ultrasonicRear.displayValue, 'NA');
  });

  test(
    'does not treat malformed sensor frames or timestamps as fresh data',
    () {
      final malformedSensor = parseTelemetryEvent(
        '{"type":"esp32_line",'
        '"line":"TEL|0|SENSORS|TOF_L|-1|TOF_C|FAR|TOF_R|390|US_REAR|NA",'
        '"received_at":"2026-11-07T12:00:00Z"}',
      ) as Esp32LineEvent;
      expect(malformedSensor.sensorFrame, isNull);
      expect(malformedSensor.sensorParseError, isNotNull);

      expect(
        parseTelemetryEvent('{"type":"esp32_line","line":"READY"}'),
        isA<MalformedTelemetryEvent>(),
      );
      expect(
        parseTelemetryEvent(
          '{"type":"esp32_line","line":"READY",'
          '"received_at":"2026-11-07T12:00:00"}',
        ),
        isA<MalformedTelemetryEvent>(),
      );
    },
  );

  test('preserves an unknown event type without throwing', () {
    expect(
      parseTelemetryEvent('{"type":"future_event"}'),
      isA<UnknownTelemetryEvent>(),
    );
  });

  test('returns malformed for invalid JSON and invalid known-event fields', () {
    expect(parseTelemetryEvent('{bad json'), isA<MalformedTelemetryEvent>());
    expect(
      parseTelemetryEvent(
        '{"type":"esp32_line","line":42,'
        '"received_at":"2026-11-06T12:00:00Z"}',
      ),
      isA<MalformedTelemetryEvent>(),
    );
    expect(parseTelemetryEvent(42), isA<MalformedTelemetryEvent>());
  });
}
