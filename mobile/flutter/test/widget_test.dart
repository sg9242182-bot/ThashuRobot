import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show SemanticsAction;
import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/app/app.dart';
import 'package:thashu_app/main.dart';
import 'package:thashu_app/services/pi_api_client.dart';
import 'package:thashu_app/widgets/zeno_offline_notice.dart';

void main() {
  testWidgets('shows Dashboard with an honest unconfigured connection state', (
    tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('ZENO controller'), findsOneWidget);
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
      'Placeholder: Controls are unavailable until the Pi connection is ready.',
      'Placeholder: App and connection settings will appear here.',
      'Placeholder: Diagnostics will appear when data is available.',
      'Placeholder: Developer and recovery tools are not available yet.',
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

}

class _FakePiTransport implements PiApiTransport {
  _FakePiTransport(this.responses);

  final List<PiApiHttpResponse> responses;
  Uri? lastUri;
  Uri? lastPostUri;
  Object? lastJsonBody;

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
    return responses.removeAt(0);
  }

  @override
  void close() {}
}
