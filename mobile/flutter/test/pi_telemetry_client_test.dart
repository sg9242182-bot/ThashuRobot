import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/models/telemetry_event.dart';
import 'package:thashu_app/services/pi_telemetry_client.dart';

void main() {
  test(
    'connects to the documented path with bearer auth and parses events',
    () async {
      final transport = _FakeTelemetryTransport();
      final client = PiTelemetryClient(
        baseUri: Uri.parse('https://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );
      final event = Completer<TelemetryEvent>();
      final subscription = client.events.listen(event.complete);

      await client.connect();

      expect(client.state, TelemetryConnectionState.connected);
      expect(transport.uri, Uri.parse('wss://pi.test:8000/api/v1/telemetry'));
      expect(transport.headers, {'Authorization': 'Bearer test-token'});

      transport.socket.add(
        '{"type":"command_result","command_id":"cmd-4",'
        '"status":"acknowledged","error_code":null,'
        '"timestamp":"2026-11-06T12:00:00Z"}',
      );
      expect(await event.future, isA<CommandResultEvent>());
      expect(client.hasCurrentConnectionEvent, isTrue);
      await subscription.cancel();
      await client.dispose();
      expect(client.state, TelemetryConnectionState.disconnected);
    },
  );

  test('uses ws for an HTTP base URL', () async {
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: _FakeTelemetryTransport(),
    );

    expect(
      client.telemetryUri,
      Uri.parse('ws://pi.test:8000/api/v1/telemetry'),
    );
    await client.dispose();
  });

  test(
    'stores the latest valid sensor frame and its Pi receive timestamp',
    () async {
      final transport = _FakeTelemetryTransport();
      final client = PiTelemetryClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );

      await client.connect();
      transport.socket.add(
        '{"type":"esp32_line",'
        '"line":"TEL|7|SENSORS|TOF_L|420|TOF_C|FAR|TOF_R|390|US_REAR|NA",'
        '"received_at":"2026-11-07T12:00:00.123Z"}',
      );
      await Future<void>.delayed(Duration.zero);

      expect(client.latestSensorFrame?.sequence, 7);
      expect(client.latestSensorFrame?.tofCenter.displayValue, 'FAR');
      expect(client.latestSensorFrame?.ultrasonicRear.displayValue, 'NA');
      expect(
        client.latestSensorPiReceivedAt,
        DateTime.utc(2026, 11, 7, 12, 0, 0, 123),
      );
      expect(client.latestSensorFrameReceivedAt, isNotNull);

      await client.dispose();
    },
  );

  test('missing token fails safely without opening a socket', () async {
    final transport = _FakeTelemetryTransport();
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: null,
      transport: transport,
    );

    await client.connect();

    expect(client.state, TelemetryConnectionState.failed);
    expect(transport.uri, isNull);
    expect(client.lastError, isNotNull);
    await client.dispose();
  });

  test('transport errors move the client to failed state', () async {
    final transport = _FakeTelemetryTransport()
      ..connectError = StateError('connection failed');
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );

    await client.connect();

    expect(client.state, TelemetryConnectionState.failed);
    expect(client.lastError, isA<StateError>());
    await client.dispose();
  });

  test('server disconnect can be reconnected explicitly', () async {
    final transport = _FakeTelemetryTransport();
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );

    await client.connect();
    final disconnected = client.states.firstWhere(
      (state) => state == TelemetryConnectionState.disconnected,
    );
    await transport.socket.close();
    expect(await disconnected, TelemetryConnectionState.disconnected);
    expect(client.hasCurrentConnectionEvent, isFalse);

    final reconnecting = client.states.firstWhere(
      (state) => state == TelemetryConnectionState.reconnecting,
    );
    final reconnect = client.connect();
    expect(await reconnecting, TelemetryConnectionState.reconnecting);
    await reconnect;
    expect(client.state, TelemetryConnectionState.connected);
    expect(client.hasCurrentConnectionEvent, isFalse);

    await client.dispose();
  });

  test('a socket error is cleaned up before an explicit retry', () async {
    final transport = _FakeTelemetryTransport();
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );

    await client.connect();
    final failed = client.states.firstWhere(
      (state) => state == TelemetryConnectionState.failed,
    );
    final oldSocket = transport.socket;
    oldSocket.fail(StateError('socket failed'));
    expect(await failed, TelemetryConnectionState.failed);

    await client.connect();

    expect(transport.sockets, hasLength(2));
    expect(oldSocket.isClosed, isTrue);
    expect(client.state, TelemetryConnectionState.connected);
    await client.dispose();
  });
}

class _FakeTelemetryTransport implements PiTelemetryTransport {
  final sockets = <_FakeTelemetrySocket>[];
  _FakeTelemetrySocket get socket => sockets.last;
  Uri? uri;
  Map<String, String>? headers;
  Object? connectError;

  @override
  Future<PiTelemetrySocket> connect(
    Uri uri, {
    required Map<String, String> headers,
  }) async {
    this.uri = uri;
    this.headers = headers;
    if (connectError case final error?) throw error;
    final socket = _FakeTelemetrySocket();
    sockets.add(socket);
    return socket;
  }
}

class _FakeTelemetrySocket implements PiTelemetrySocket {
  final _controller = StreamController<Object?>.broadcast();
  bool isClosed = false;

  @override
  Stream<Object?> get messages => _controller.stream;

  void add(Object? message) => _controller.add(message);

  void fail(Object error) => _controller.addError(error);

  @override
  Future<void> close() {
    isClosed = true;
    return _controller.close();
  }
}
