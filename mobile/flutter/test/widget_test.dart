import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show SemanticsAction;
import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/app/app.dart';
import 'package:thashu_app/features/manual_control/manual_control_page.dart';
import 'package:thashu_app/main.dart';
import 'package:thashu_app/models/robot_move_request.dart';
import 'package:thashu_app/services/pi_api_client.dart';
import 'package:thashu_app/services/pi_telemetry_client.dart';
import 'package:thashu_app/widgets/zeno_offline_notice.dart';

void main() {
  testWidgets('shows Dashboard with an honest unconfigured connection state', (
    tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('Thashu Controller'), findsOneWidget);
    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.theme?.useMaterial3, isTrue);
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Pi API connection'), findsOneWidget);
    expect(find.text('Not configured'), findsOneWidget);
    expect(
      find.textContaining('Pi address is not configured yet'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('all five destinations select the matching screen', (
    tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    const titles = [
      'Dashboard',
      'Manual Control',
      'Settings',
      'Diagnostics',
      'Developer / Recovery',
    ];
    const placeholders = [
      '',
      'The Pi address and token are not configured. Controls remain disabled until the Pi API is connected.',
      'Robot connection',
      'Placeholder: Diagnostics will appear when data is available.',
      'Recovery actions unavailable',
    ];

    for (var index = 0; index < titles.length; index++) {
      await tester.tap(find.byKey(ValueKey('nav-destination-$index')));
      await tester.pumpAndSettle();

      expect(find.text(titles[index]), findsWidgets);
      if (index == 0) {
        expect(find.text('Pi API connection'), findsOneWidget);
      } else {
        expect(find.text(placeholders[index]), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('Settings exposes the current connection and onboarding fields', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(400, 4000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MyApp());

    await tester.tap(find.byKey(const ValueKey('nav-destination-2')));
    await tester.pumpAndSettle();
    expect(find.text('Robot connection'), findsOneWidget);
    expect(find.text('Connect Thashu to this phone’s hotspot'), findsOneWidget);
    expect(find.byKey(const ValueKey('hotspot-ssid-field')), findsOneWidget);
    expect(find.byKey(const ValueKey('hotspot-password-field')), findsOneWidget);
    expect(find.byKey(const ValueKey('pi-address-field')), findsOneWidget);
    expect(find.byKey(const ValueKey('pi-token-field')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('pi-certificate-fingerprint-field')),
      findsOneWidget,
    );
    expect(find.text('Competition Mode'), findsOneWidget);
    expect(
      find.textContaining('Use normal STOP to request a stop.'),
      findsOneWidget,
    );
    final openManualControl = find.text('Open Manual Control');
    await tester.ensureVisible(openManualControl);
    await tester.tap(openManualControl);
    await tester.pumpAndSettle();
    expect(find.text('Manual Control'), findsWidgets);

    await tester.tap(find.byKey(const ValueKey('nav-destination-3')));
    await tester.pumpAndSettle();
    expect(find.text('Robot self-checks unavailable'), findsOneWidget);
    expect(find.textContaining('does not provide PASS'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('nav-destination-4')));
    await tester.pumpAndSettle();
    expect(find.text('Recovery actions unavailable'), findsOneWidget);
    expect(
      find.textContaining('no shell or direct hardware commands'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('fits a common Android phone viewport without layout errors', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MyApp());
    expect(tester.takeException(), isNull);

    final semantics = tester.ensureSemantics();
    for (var index = 0; index < 5; index++) {
      final destination = find.byKey(ValueKey('nav-destination-$index'));
      final touchTarget = tester.getRect(destination);
      expect(touchTarget.width, greaterThanOrEqualTo(48));
      expect(touchTarget.height, greaterThanOrEqualTo(48));
      expect(
        tester
            .getSemantics(destination)
            .getSemanticsData()
            .hasAction(SemanticsAction.tap),
        isTrue,
      );
    }
    final refresh = find.byTooltip('Refresh robot status');
    final refreshTarget = tester.getRect(refresh);
    expect(refreshTarget.width, greaterThanOrEqualTo(48));
    expect(refreshTarget.height, greaterThanOrEqualTo(48));
    semantics.dispose();
  });

  testWidgets('reusable notice renders each explicit state', (tester) async {
    const cases = {
      ZenoNoticeState.loading: 'Loading robot information…',
      ZenoNoticeState.empty: 'No robot data is available yet.',
      ZenoNoticeState.offline:
          'Pi is not connected. Robot data and controls are unavailable.',
      ZenoNoticeState.unavailable: 'This feature is currently unavailable.',
      ZenoNoticeState.error: 'Could not load robot information.',
    };

    for (final entry in cases.entries) {
      await tester.pumpWidget(
        MaterialApp(home: ZenoOfflineNotice(state: entry.key)),
      );
      expect(find.text(entry.value), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('dashboard displays the live status fields returned by the Pi', (
    tester,
  ) async {
    final transport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
    ]);
    final client = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      transport: transport,
    );

    await tester.pumpWidget(
      MaterialApp(home: ZenoNavigationShell(apiClient: client)),
    );
    await tester.pumpAndSettle();

    expect(transport.lastUri!.path, '/api/v1/status');
    expect(find.text('Connected to Pi API'), findsOneWidget);
    expect(find.text('ESP32 transport'), findsOneWidget);
    expect(find.text('connected'), findsOneWidget);
    expect(find.text('Controller readiness'), findsOneWidget);
    expect(find.text('unknown'), findsOneWidget);
    expect(find.text('MANUAL'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'dashboard marks old status stale on failure and recovers on refresh',
    (tester) async {
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"MANUAL","controller_readiness":"unknown"}',
        ),
        const PiApiHttpResponse(statusCode: 503, body: '{"detail":"offline"}'),
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"AUTO","controller_readiness":"ready"}',
        ),
      ]);
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: ZenoNavigationShell(apiClient: client)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Connected to Pi API'), findsOneWidget);

      await tester.tap(find.byTooltip('Refresh robot status'));
      await tester.pumpAndSettle();
      expect(find.text('Unavailable'), findsOneWidget);
      expect(find.textContaining('stale'), findsWidgets);
      expect(find.text('MANUAL · stale'), findsOneWidget);

      await tester.tap(find.byTooltip('Refresh robot status'));
      await tester.pumpAndSettle();
      expect(find.text('Connected to Pi API'), findsOneWidget);
      expect(find.text('AUTO'), findsOneWidget);
      expect(find.textContaining('stale'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'dashboard shows startup failure and recovers when Pi becomes reachable',
    (tester) async {
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 503,
          body: '{"detail":"Pi is unavailable"}',
        ),
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"AUTO","controller_readiness":"unknown"}',
        ),
      ]);
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: ZenoNavigationShell(apiClient: client)),
      );
      await tester.pumpAndSettle();

      expect(transport.lastUri!.path, '/api/v1/status');
      expect(find.text('Unavailable'), findsOneWidget);
      expect(find.text('Pi is unavailable'), findsOneWidget);
      expect(find.text('Connected to Pi API'), findsNothing);

      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();

      expect(find.text('Connected to Pi API'), findsOneWidget);
      expect(find.text('Unavailable'), findsNothing);
      expect(find.text('AUTO'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('manual movement stays disabled until Pi reports MANUAL mode', (
    tester,
  ) async {
    _useTallManualViewport(tester);
    await tester.pumpWidget(const MaterialApp(home: _ManualControlHarness()));
    final unconfiguredForward = tester.widget<FilledButton>(
      find.byKey(const ValueKey('move-forward-button')),
    );
    expect(unconfiguredForward.onPressed, isNull);
    expect(find.text('Not configured'), findsOneWidget);

    final transport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"AUTO","controller_readiness":"unknown"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body: '{"mode":"MANUAL","status":"switched"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
    ]);
    final client = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );
    await tester.pumpWidget(
      MaterialApp(home: _ManualControlHarness(apiClient: client)),
    );
    await tester.pumpAndSettle();
    await _scrollTo(tester, find.byKey(const ValueKey('manual-stop-button')));

    await _scrollTo(tester, find.byKey(const ValueKey('move-forward-button')));
    final autoForward = tester.widget<FilledButton>(
      find.byKey(const ValueKey('move-forward-button')),
    );
    await _scrollTo(tester, find.byKey(const ValueKey('manual-stop-button')));
    final stop = tester.widget<FilledButton>(
      find.byKey(const ValueKey('manual-stop-button')),
    );
    expect(autoForward.onPressed, isNull);
    expect(stop.onPressed, isNotNull);
    expect(find.text('AUTO'), findsWidgets);

    await _scrollTo(tester, find.byKey(const ValueKey('mode-manual-button')));
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('mode-manual-button')),
          )
          .onPressed,
      isNotNull,
    );
    await tester.tap(find.byKey(const ValueKey('mode-manual-button')));
    await tester.pumpAndSettle();
    expect(transport.lastPostUri!.path, '/api/v1/robot/mode');
    expect(transport.lastJsonBody, {'mode': 'MANUAL'});
    await _scrollTo(tester, find.byKey(const ValueKey('move-forward-button')));
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('move-forward-button')),
          )
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('held movement renews every 250ms and release stops renewals', (
    tester,
  ) async {
    _useTallManualViewport(tester);
    final transport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
      const PiApiHttpResponse(
        statusCode: 202,
        body:
            '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
            '"command_id":"lease-1","lease_id":"lease-1","command":"forward",'
            '"status":"dispatched","control_mode":"MANUAL",'
            '"error_code":null,"timestamp":"2026-11-10T12:00:00Z"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"lease_id":"lease-1","status":"active",'
            '"expires_at":"2026-11-10T12:00:00Z"}',
      ),
    ]);
    final client = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );
    await tester.pumpWidget(
      MaterialApp(home: _ManualControlHarness(apiClient: client)),
    );
    await tester.pumpAndSettle();
    final button = find.byKey(const ValueKey('move-forward-button'));
    await _scrollTo(tester, button);
    final gesture = await tester.startGesture(tester.getCenter(button));
    await tester.pump();
    await tester.pump();
    expect(transport.postCount, 1);

    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump();
    expect(transport.postCount, 2);
    expect(transport.lastPostUri!.path, '/api/v1/robot/commands/lease-1/renew');
    expect(transport.lastJsonBody, containsPair('request_id', isA<String>()));

    await gesture.up();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));
    expect(transport.postCount, 2);
  });

  testWidgets('STOP cancels held movement lease renewals', (tester) async {
    _useTallManualViewport(tester);
    final transport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
      const PiApiHttpResponse(
        statusCode: 202,
        body:
            '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
            '"command_id":"lease-1","lease_id":"lease-1","command":"forward",'
            '"status":"dispatched","control_mode":"MANUAL",'
            '"error_code":null,"timestamp":"2026-11-10T12:00:00Z"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"lease_id":"lease-1","status":"active",'
            '"expires_at":"2026-11-10T12:00:00Z"}',
      ),
      const PiApiHttpResponse(
        statusCode: 202,
        body:
            '{"request_id":"c1234567-89ab-4cde-8f01-23456789abcd",'
            '"command_id":"cmd-stop","command":"stop","status":"dispatched",'
            '"control_mode":"MANUAL","error_code":null,'
            '"timestamp":"2026-11-10T12:00:01Z"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
    ]);
    final client = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );
    await tester.pumpWidget(
      MaterialApp(home: _ManualControlHarness(apiClient: client)),
    );
    await tester.pumpAndSettle();
    final forward = find.byKey(const ValueKey('move-forward-button'));
    await _scrollTo(tester, forward);
    final gesture = await tester.startGesture(tester.getCenter(forward));
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump();
    expect(transport.postCount, 2);

    final stop = find.byKey(const ValueKey('manual-stop-button'));
    await tester.tap(stop);
    await tester.pumpAndSettle();
    expect(transport.lastPostUri!.path, '/api/v1/robot/stop');
    expect(transport.postCount, 3);

    await tester.pump(const Duration(milliseconds: 750));
    expect(transport.postCount, 3);
    await gesture.up();
    await tester.pump();
  });

  testWidgets('telemetry disconnect stops lease renewals', (tester) async {
    _useTallManualViewport(tester);
    final telemetryTransport = _FakePiTelemetryTransport();
    final telemetryClient = PiTelemetryClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: telemetryTransport,
    );
    final apiTransport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
      const PiApiHttpResponse(
        statusCode: 202,
        body:
            '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
            '"command_id":"lease-1","lease_id":"lease-1","command":"forward",'
            '"status":"dispatched","control_mode":"MANUAL",'
            '"error_code":null,"timestamp":"2026-11-10T12:00:00Z"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"lease_id":"lease-1","status":"active",'
            '"expires_at":"2026-11-10T12:00:00Z"}',
      ),
    ]);
    final apiClient = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: apiTransport,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: _ManualControlHarness(
          apiClient: apiClient,
          telemetryClient: telemetryClient,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(telemetryClient.state, TelemetryConnectionState.connected);

    final forward = find.byKey(const ValueKey('move-forward-button'));
    await _scrollTo(tester, forward);
    final gesture = await tester.startGesture(tester.getCenter(forward));
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump();
    expect(apiTransport.postCount, 2);

    await telemetryClient.disconnect();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 750));
    expect(apiTransport.postCount, 2);

    await gesture.up();
    await tester.pump();
    await tester.pumpWidget(const SizedBox.shrink());
    await telemetryClient.dispose();
  });

  testWidgets(
    'manual move disables repeats while pending and reports dispatch honestly',
    (tester) async {
      _useTallManualViewport(tester);
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"MANUAL","controller_readiness":"unknown"}',
        ),
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"acknowledged","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-06T12:00:01Z"}',
        ),
      ]);
      final postResponse = Completer<PiApiHttpResponse>();
      transport.postCompleter = postResponse;
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: _ManualControlHarness(apiClient: client)),
      );
      await tester.pumpAndSettle();
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      await tester.tap(find.byKey(const ValueKey('move-forward-button')));
      await tester.pump();

      expect(transport.postCount, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('move-forward-button')),
            )
            .onPressed,
        isNull,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('manual-stop-button')),
            )
            .onPressed,
        isNotNull,
      );

      postResponse.complete(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"dispatched","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-06T12:00:00Z"}',
        ),
      );
      await tester.pumpAndSettle();

      expect(transport.lastPostUri!.path, '/api/v1/robot/move');
      final sentMove = transport.lastJsonBody! as Map<String, dynamic>;
      expect(sentMove['request_id'], isA<String>());
      expect(sentMove['direction'], 'forward');
      expect(sentMove['speed'], 200);
      expect(find.text('Command status: dispatched'), findsOneWidget);
      await _scrollTo(tester, find.text('Check command result'));
      expect(find.text('Command status: dispatched'), findsOneWidget);
      expect(find.textContaining('not confirmed'), findsOneWidget);
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('move-forward-button')),
            )
            .onPressed,
        isNull,
      );

      await tester.tap(find.text('Check command result'));
      await tester.pumpAndSettle();
      await _scrollTo(tester, find.text('Command status: acknowledged'));
      expect(find.text('Command status: acknowledged'), findsOneWidget);
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('move-forward-button')),
            )
            .onPressed,
        isNotNull,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'STOP remains available and reports that physical stopping is unconfirmed',
    (tester) async {
      _useTallManualViewport(tester);
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"AUTO","controller_readiness":"unknown"}',
        ),
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"command_id":"cmd-stop","command":"stop",'
              '"status":"dispatched","control_mode":"AUTO",'
              '"error_code":null,"timestamp":"2026-11-06T12:00:00Z"}',
        ),
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"AUTO","controller_readiness":"unknown"}',
        ),
      ]);
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: _ManualControlHarness(apiClient: client)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('manual-stop-button')));
      await tester.pumpAndSettle();

      expect(transport.lastPostUri!.path, '/api/v1/robot/stop');
      _expectStopRequestBody(transport.lastJsonBody);
      expect(
        find.textContaining('physical stopping is not confirmed'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('manual control reports safety rejection and ACK timeout', (
    tester,
  ) async {
    _useTallManualViewport(tester);
    const outcomes = {
      'safety_error': 'The robot rejected forward for safety: obstacle.',
      'timed_out': 'forward acknowledgement timed out.',
    };

    for (final outcome in outcomes.entries) {
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"MANUAL","controller_readiness":"unknown"}',
        ),
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"dispatched","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-06T12:00:00Z"}',
        ),
        PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"${outcome.key}","control_mode":"MANUAL",'
              '"error_code":"${outcome.key == 'safety_error' ? 'obstacle' : 'esp32_ack_timeout'}",'
              '"timestamp":"2026-11-06T12:00:01Z"}',
        ),
      ]);
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: _ManualControlHarness(apiClient: client)),
      );
      await tester.pumpAndSettle();
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      await tester.tap(find.byKey(const ValueKey('move-forward-button')));
      await tester.pumpAndSettle();
      await _scrollTo(tester, find.text('Check command result'));
      await tester.tap(find.text('Check command result'));
      await tester.pumpAndSettle();
      await _scrollTo(tester, find.textContaining(outcome.value));
      await _scrollTo(tester, find.byKey(const ValueKey('manual-stop-button')));

      expect(find.textContaining(outcome.value), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('manual-stop-button')),
            )
            .onPressed,
        isNotNull,
      );
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets(
    'network loss marks command outcome unknown and leaves STOP available',
    (tester) async {
      _useTallManualViewport(tester);
      final transport = _FakePiTransport([
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"MANUAL","controller_readiness":"unknown"}',
        ),
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"command_id":"cmd-stop","command":"stop",'
              '"status":"dispatched","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-06T12:00:00Z"}',
        ),
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"api":"ok","esp32_transport":"connected",'
              '"control_mode":"MANUAL","controller_readiness":"unknown"}',
        ),
      ])..postFailure = const SocketException('connection closed');
      final client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );

      await tester.pumpWidget(
        MaterialApp(home: _ManualControlHarness(apiClient: client)),
      );
      await tester.pumpAndSettle();
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      await tester.tap(find.byKey(const ValueKey('move-forward-button')));
      await tester.pumpAndSettle();

      await _scrollTo(tester, find.textContaining('outcome may be unknown'));
      expect(find.textContaining('outcome may be unknown'), findsOneWidget);
      await tester.drag(find.byType(ListView), const Offset(0, 1200));
      await tester.pumpAndSettle();
      expect(find.textContaining('MANUAL · stale'), findsOneWidget);
      await _scrollTo(
        tester,
        find.byKey(const ValueKey('move-forward-button')),
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('move-forward-button')),
            )
            .onPressed,
        isNull,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const ValueKey('manual-stop-button')),
            )
            .onPressed,
        isNotNull,
      );

      await _scrollTo(tester, find.byKey(const ValueKey('manual-stop-button')));
      await tester.tap(find.byKey(const ValueKey('manual-stop-button')));
      await tester.pumpAndSettle();
      expect(transport.lastPostUri!.path, '/api/v1/robot/stop');
      _expectStopRequestBody(transport.lastJsonBody);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('pausing never claims STOP and resume refreshes Pi status', (
    tester,
  ) async {
    _useTallManualViewport(tester);
    final transport = _FakePiTransport([
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
      const PiApiHttpResponse(
        statusCode: 200,
        body:
            '{"api":"ok","esp32_transport":"connected",'
            '"control_mode":"MANUAL","controller_readiness":"unknown"}',
      ),
    ]);
    final client = PiApiClient(
      baseUri: Uri.parse('http://pi.test:8000'),
      bearerToken: 'test-token',
      transport: transport,
    );

    await tester.pumpWidget(
      MaterialApp(home: _ManualControlHarness(apiClient: client)),
    );
    await tester.pumpAndSettle();
    await _scrollTo(tester, find.byKey(const ValueKey('move-forward-button')));
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('move-forward-button')),
          )
          .onPressed,
      isNotNull,
    );

    final lifecycleObserver = tester.state(find.byType(ManualControlPage));
    (lifecycleObserver as dynamic).didChangeAppLifecycleState(
      AppLifecycleState.paused,
    );
    await tester.pump();
    expect(transport.postCount, 0);
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('move-forward-button')),
          )
          .onPressed,
      isNull,
    );
    await _scrollTo(tester, find.byKey(const ValueKey('manual-stop-button')));
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('manual-stop-button')),
          )
          .onPressed,
      isNotNull,
    );

    (lifecycleObserver as dynamic).didChangeAppLifecycleState(
      AppLifecycleState.resumed,
    );
    await tester.pumpAndSettle();
    expect(transport.lastUri!.path, '/api/v1/status');
    expect(find.text('MANUAL'), findsWidgets);
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const ValueKey('move-forward-button')),
          )
          .onPressed,
      isNotNull,
    );
    expect(tester.takeException(), isNull);
  });
}

void _expectStopRequestBody(Object? body) {
  expect(body, isA<Map<String, dynamic>>());
  final requestId = (body as Map<String, dynamic>)['request_id'];
  expect(requestId, isA<String>());
  expect(RobotRequestId.isValid(requestId as String), isTrue);
}

class _ManualControlHarness extends StatelessWidget {
  const _ManualControlHarness({this.apiClient, this.telemetryClient});

  final PiApiClient? apiClient;
  final PiTelemetryClient? telemetryClient;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: ManualControlPage(
      apiClient: apiClient,
      telemetryClient: telemetryClient,
    ),
  );
}

void _useTallManualViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(400, 4000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      finder,
      240,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

class _FakePiTelemetryTransport implements PiTelemetryTransport {
  final _FakePiTelemetrySocket socket = _FakePiTelemetrySocket();

  @override
  Future<PiTelemetrySocket> connect(
    Uri uri, {
    required Map<String, String> headers,
  }) async => socket;
}

class _FakePiTelemetrySocket implements PiTelemetrySocket {
  final _messages = StreamController<Object?>.broadcast();

  @override
  Stream<Object?> get messages => _messages.stream;

  @override
  Future<void> close() => _messages.close();
}

class _FakePiTransport implements PiApiTransport {
  _FakePiTransport(this.responses);

  final List<PiApiHttpResponse> responses;
  Uri? lastUri;
  Uri? lastPostUri;
  Object? lastJsonBody;
  int postCount = 0;
  Completer<PiApiHttpResponse>? postCompleter;
  Object? postFailure;

  @override
  Future<PiApiHttpResponse> get(
    Uri uri, {
    required Map<String, String> headers,
  }) async {
    lastUri = uri;
    return responses.removeAt(0);
  }

  @override
  Future<PiApiHttpResponse> post(
    Uri uri, {
    required Map<String, String> headers,
    Object? jsonBody,
  }) async {
    lastUri = uri;
    lastPostUri = uri;
    lastJsonBody = jsonBody;
    postCount++;
    final pending = postCompleter;
    postCompleter = null;
    if (pending != null) return pending.future;
    final failure = postFailure;
    postFailure = null;
    if (failure != null) throw failure;
    return responses.removeAt(0);
  }

  @override
  void close() {}
}
