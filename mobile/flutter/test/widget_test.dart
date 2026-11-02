import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show SemanticsAction;
import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/main.dart';
import 'package:thashu_app/widgets/zeno_offline_notice.dart';

void main() {
  testWidgets(
    'shows Dashboard and clearly labels its content as a placeholder',
    (tester) async {
      await tester.pumpWidget(const MyApp());

      expect(find.text('ZENO controller'), findsOneWidget);
      final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(app.theme?.useMaterial3, isTrue);
      expect(find.text('Dashboard'), findsWidgets);
      expect(find.textContaining('Pi is not connected'), findsOneWidget);
      expect(
        find.text('Placeholder: Robot overview will appear here.'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('all five destinations select the matching placeholder screen', (
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
      'Placeholder: Robot overview will appear here.',
      'Placeholder: Controls are unavailable until the Pi connection is ready.',
      'Placeholder: App and connection settings will appear here.',
      'Placeholder: Diagnostics will appear when data is available.',
      'Placeholder: Developer and recovery tools are not available yet.',
    ];

    for (var index = 0; index < titles.length; index++) {
      await tester.tap(find.byType(NavigationDestination).at(index));
      await tester.pumpAndSettle();

      final navigationBar = tester.widget<NavigationBar>(
        find.byType(NavigationBar),
      );
      expect(navigationBar.selectedIndex, index);
      expect(find.text(titles[index]), findsWidgets);
      expect(find.text(placeholders[index]), findsOneWidget);
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
      final destination = find.byType(NavigationDestination).at(index);
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
}
