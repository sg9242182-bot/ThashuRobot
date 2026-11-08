import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

class WifiProvisioningClient {
  static const serviceUuid = '8c6d0001-7a4b-4f61-b7a5-927f4e2a1000';
  static const credentialsUuid = '8c6d0002-7a4b-4f61-b7a5-927f4e2a1000';
  static const statusUuid = '8c6d0003-7a4b-4f61-b7a5-927f4e2a1000';

  Future<String> provision({
    required String ssid,
    required String password,
  }) async {
    final ssidBytes = utf8.encode(ssid);
    if (ssidBytes.isEmpty || ssidBytes.length > 32) {
      throw const FormatException('SSID must be 1 to 32 UTF-8 bytes.');
    }
    final passwordBytes = utf8.encode(password);
    final validPsk = (passwordBytes.length >= 8 && passwordBytes.length <= 63) ||
        (password.length == 64 && RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(password));
    if (!validPsk || password.contains(RegExp(r'[\r\n\x00]'))) {
      throw const FormatException('Use a WPA2 password with 8–63 characters.');
    }

    await _requestBluetoothPermissions();
    if (!await FlutterBluePlus.isSupported) {
      throw StateError('This phone does not support Bluetooth LE.');
    }
    await FlutterBluePlus.adapterState
        .where((state) => state == BluetoothAdapterState.on)
        .first
        .timeout(const Duration(seconds: 20), onTimeout: () {
      throw StateError('Turn on Bluetooth, then try again.');
    });

    BluetoothDevice? device;
    StreamSubscription<List<ScanResult>>? scanSubscription;
    try {
      final found = Completer<BluetoothDevice>();
      scanSubscription = FlutterBluePlus.scanResults.listen((results) {
        for (final result in results) {
          final advertisesService = result.advertisementData.serviceUuids.any(
            (uuid) => uuid.toString().toLowerCase() == serviceUuid,
          );
          if (advertisesService && !found.isCompleted) {
            found.complete(result.device);
          }
        }
      });
      await FlutterBluePlus.startScan(
        withServices: [Guid(serviceUuid)],
        timeout: const Duration(seconds: 20),
      );
      device = await found.future.timeout(
        const Duration(seconds: 22),
        onTimeout: () => throw StateError(
          'Thashu was not found. Hold the Pi button for 3 seconds, then scan again.',
        ),
      );
      await FlutterBluePlus.stopScan();
      await device.connect();
      final services = await device.discoverServices();
      final service = _firstOrNull(
        services.where(
          (entry) => entry.uuid.toString().toLowerCase() == serviceUuid,
        ),
      );
      if (service == null) {
        throw StateError('The Thashu setup service was not found.');
      }
      final credentials = _firstOrNull(
        service.characteristics.where(
          (entry) => entry.uuid.toString().toLowerCase() == credentialsUuid,
        ),
      );
      final status = _firstOrNull(
        service.characteristics.where(
          (entry) => entry.uuid.toString().toLowerCase() == statusUuid,
        ),
      );
      if (credentials == null || status == null) {
        throw StateError('The Thashu setup characteristics are incomplete.');
      }

      final payload = utf8.encode(jsonEncode({'ssid': ssid, 'password': password}));
      // Reliable long writes let the full credential object fit even when the
      // negotiated BLE MTU is small. The Pi characteristic enables this mode.
      await credentials.write(payload, withoutResponse: false, allowLongWrite: true);

      final deadline = DateTime.now().add(const Duration(seconds: 35));
      var lastStatus = 'received';
      while (DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(seconds: 2));
        try {
          lastStatus = utf8.decode(await status.read()).trim();
        } on Exception {
          // A phone hotspot transition can briefly interrupt the BLE link.
          continue;
        }
        if (lastStatus == 'connected') return 'Connected to the phone hotspot.';
        if (lastStatus == 'failed') {
          throw StateError(
            'The Pi could not join that hotspot. Check the SSID/password and hotspot WPA2 setting.',
          );
        }
        if (lastStatus == 'invalid' || lastStatus == 'expired') {
          throw StateError('The Pi setup window expired. Hold its button and retry.');
        }
      }
      return lastStatus == 'connecting' || lastStatus == 'received'
          ? 'Credentials sent. The Pi is still joining the hotspot; check the Pi status shortly.'
          : 'The Pi did not confirm the Wi-Fi connection. Check the Pi status.';
    } finally {
      await FlutterBluePlus.stopScan();
      await scanSubscription?.cancel();
      if (device != null && device.isConnected) {
        await device.disconnect();
      }
    }
  }

  T? _firstOrNull<T>(Iterable<T> values) {
    final iterator = values.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }

  Future<void> _requestBluetoothPermissions() async {
    if (Platform.isAndroid) {
      final results = await <Permission>[
        Permission.bluetoothScan,
        Permission.bluetoothConnect,
      ].request();
      if (results.values.any((status) => !status.isGranted)) {
        throw StateError('Allow Bluetooth scan and connect permissions for setup.');
      }
    } else if (Platform.isIOS) {
      final status = await Permission.bluetooth.request();
      if (!status.isGranted) {
        throw StateError('Allow Bluetooth access in the phone settings.');
      }
    }
  }
}
