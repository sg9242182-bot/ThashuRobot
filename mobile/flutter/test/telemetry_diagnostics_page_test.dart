import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/features/diagnostics/telemetry_diagnostics_page.dart';
import 'package:thashu_app/services/pi_telemetry_client.dart';

void main() {
  testWidgets('shows stream updates and stale state after disconnect', (
    tester,
  ) async {
    final transport = _FakeTelemetryTransport();
    final client = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: TelemetryDiagnosticsPage(client: client)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Telemetry socket'), findsOneWidget);
    expect(find.text('Connected'), findsOneWidget);
    expect(find.text('Waiting for telemetry events.'), findsOneWidget);

    transport.socket.add(
      '{"type":"command_result","command_id":"cmd-9",'
      '"status":"acknowledged","error_code":null,'
      '"timestamp":"2026-11-06T12:00:00Z"}',
    );
    await tester.pumpAndSettle();
    expect(find.text('Command result'), findsOneWidget);
    expect(find.text('cmd-9'), findsOneWidget);
    expect(
      find.text(
        'Last message is stale: this connection has not received a new event.',
      ),
      findsNothing,
    );

    final disconnected = client.states.firstWhere(
      (state) => state == TelemetryConnectionState.disconnected,
    );
    await transport.socket.close();
    await disconnected;
    await tester.pumpAndSettle();
    expect(find.text('Disconnected'), findsOneWidget);
    expect(
      find.text(
        'Last message is stale: this connection has not received a new event.',
      ),
      findsOneWidget,
    );

    await tester.pumpWidget(const SizedBox.shrink());
    await client.dispose();
    expect(transport.socket.isClosed, isTrue);
  });

  testWidgets(
    'renders sensor readings fresh for one second and refreshes on the next frame',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final transport = _FakeTelemetryTransport();
      final client = PiTelemetryClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );
      addTearDown(client.dispose);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: TelemetryDiagnosticsPage(client: client)),
        ),
      );
      await tester.pump();
      await tester.pump();

      transport.socket.add(_sensorEvent('420', 'FAR', '390', 'NA'));
      await tester.pump();
      await tester.pump();
      expect(client.latestSensorFrame, isNotNull);
      expect(find.text('Fresh'), findsOneWidget);
      expect(find.text('420 mm'), findsOneWidget);
      expect(find.text('FAR'), findsOneWidget);
      expect(find.text('NA'), findsOneWidget);
      expect(find.text('Pi received at'), findsOneWidget);

      await tester.pump(const Duration(seconds: 1));
      expect(find.text('Stale'), findsOneWidget);

      transport.socket.add(_sensorEvent('invalid', 'FAR', '390', 'NA'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Stale'), findsOneWidget);

      transport.socket.add(_sensorEvent('NA', 'FAR', 'NA', 'FAR'));
      await tester.pump();
      await tester.pump();
      expect(client.latestSensorFrame?.tofLeft.displayValue, 'NA');
      expect(find.text('Fresh'), findsOneWidget);
      expect(find.text('Stale'), findsNothing);
      expect(find.text('FAR'), findsNWidgets(2));
      expect(find.text('NA'), findsNWidgets(2));

      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

String _sensorEvent(String left, String center, String right, String rear) =>
    '{"type":"esp32_line",'
    '"line":"TEL|0|SENSORS|TOF_L|$left|TOF_C|$center|'
    'TOF_R|$right|US_REAR|$rear",'
    '"received_at":"2026-11-07T12:00:00.123Z"}';

class _FakeTelemetryTransport implements PiTelemetryTransport {
  final sockets = <_FakeTelemetrySocket>[];
  _FakeTelemetrySocket get socket => sockets.last;

  @override
  Future<PiTelemetrySocket> connect(
    Uri uri, {
    required Map<String, String> headers,
  }) async {
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

  void add(Object? frame) => _controller.add(frame);

  @override
  Future<void> close() {
    isClosed = true;
    return _controller.close();
  }
}
