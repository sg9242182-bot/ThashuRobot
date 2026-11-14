import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/features/settings/settings_page.dart';
import 'package:thashu_app/services/wifi_provisioning_client.dart';

void main() {
  const handoff = PiConnectionHandoff(
    apiBaseUrl: 'https://192.168.1.42:8443',
    serverCertSha256:
        'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    apiToken: 'temporary-test-token',
  );

  testWidgets('BLE handoff prefills settings but requires an explicit save', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(400, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final provisioning = _FakeWifiProvisioningService(result: handoff);
    final saved = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SettingsPage(
            wifiProvisioningClient: provisioning,
            onSaveConnectionWithPin: (address, token, pin) async {
              saved
                ..add(address)
                ..add(token)
                ..add(pin);
              return 'Saved securely.';
            },
          ),
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const ValueKey('hotspot-ssid-field')),
      'Robot hotspot',
    );
    await tester.enterText(
      find.byKey(const ValueKey('hotspot-password-field')),
      'test-password',
    );
    await tester.tap(find.byKey(const ValueKey('provision-hotspot-button')));
    await tester.pumpAndSettle();

    expect(provisioning.ssid, 'Robot hotspot');
    expect(provisioning.password, 'test-password');
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('hotspot-ssid-field')))
          .controller!
          .text,
      isEmpty,
    );
    expect(
      tester
          .widget<TextField>(
            find.byKey(const ValueKey('hotspot-password-field')),
          )
          .controller!
          .text,
      isEmpty,
    );
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('pi-address-field')))
          .controller!
          .text,
      handoff.apiBaseUrl,
    );
    expect(
      tester
          .widget<TextField>(
            find.byKey(const ValueKey('pi-certificate-fingerprint-field')),
          )
          .controller!
          .text,
      handoff.serverCertSha256,
    );
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('pi-token-field')))
          .controller!
          .text,
      handoff.apiToken,
    );
    expect(saved, isEmpty);

    await tester.tap(find.byKey(const ValueKey('save-pi-connection-button')));
    await tester.pumpAndSettle();
    expect(saved, [
      handoff.apiBaseUrl,
      handoff.apiToken,
      handoff.serverCertSha256,
    ]);
    expect(find.textContaining('Saved securely.'), findsOneWidget);
  });

  testWidgets('failed provisioning clears hotspot inputs and reports failure', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(400, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SettingsPage(
            wifiProvisioningClient: _FakeWifiProvisioningService(
              failure: StateError('setup window expired'),
            ),
          ),
        ),
      ),
    );
    await tester.enterText(
      find.byKey(const ValueKey('hotspot-ssid-field')),
      'Robot hotspot',
    );
    await tester.enterText(
      find.byKey(const ValueKey('hotspot-password-field')),
      'test-password',
    );
    await tester.tap(find.byKey(const ValueKey('provision-hotspot-button')));
    await tester.pumpAndSettle();

    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('hotspot-ssid-field')))
          .controller!
          .text,
      isEmpty,
    );
    expect(
      tester
          .widget<TextField>(
            find.byKey(const ValueKey('hotspot-password-field')),
          )
          .controller!
          .text,
      isEmpty,
    );
    expect(find.textContaining('setup window expired'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

class _FakeWifiProvisioningService implements WifiProvisioningService {
  _FakeWifiProvisioningService({this.result, this.failure});

  final PiConnectionHandoff? result;
  final Object? failure;
  String? ssid;
  String? password;

  @override
  Future<PiConnectionHandoff> provision({
    required String ssid,
    required String password,
    void Function(String status)? onStatus,
  }) async {
    this.ssid = ssid;
    this.password = password;
    onStatus?.call('found');
    onStatus?.call('waiting');
    if (failure != null) throw failure!;
    onStatus?.call('credentials_sent');
    onStatus?.call('connecting');
    onStatus?.call('connected');
    return result!;
  }
}
