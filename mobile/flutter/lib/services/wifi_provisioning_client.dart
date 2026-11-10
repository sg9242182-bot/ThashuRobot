import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

import 'pinned_pi_tls.dart';

class PiConnectionHandoff {
  const PiConnectionHandoff({
    required this.apiBaseUrl,
    required this.serverCertSha256,
    required this.apiToken,
  });

  final String apiBaseUrl;
  final String serverCertSha256;
  final String apiToken;

  static PiConnectionHandoff fromBytes(List<int> bytes) {
    try {
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is! Map<String, dynamic> ||
          decoded.keys.toSet().difference({
            'api_base_url',
            'server_cert_sha256',
            'api_token',
          }).isNotEmpty ||
          decoded.keys.toSet().length != 3 ||
          decoded.values.any((value) => value is! String)) {
        throw const FormatException('Connection info must contain exactly api_base_url, server_cert_sha256, and api_token.');
      }

      final apiBaseUrl = decoded['api_base_url'] as String;
      final pin = decoded['server_cert_sha256'] as String;
      final token = decoded['api_token'] as String;
      final uri = Uri.tryParse(apiBaseUrl);
      final address = uri == null ? null : InternetAddress.tryParse(uri.host);
      if (uri == null ||
          uri.scheme != 'https' ||
          !uri.hasAuthority ||
          uri.userInfo.isNotEmpty ||
          uri.path.isNotEmpty ||
          uri.hasQuery ||
          uri.hasFragment ||
          uri.port != 8443 ||
          address?.type != InternetAddressType.IPv4 ||
          !RegExp(r'^[0-9a-f]{64}$').hasMatch(pin) ||
          token.isEmpty ||
          token.trim() != token ||
          token.contains(RegExp(r'\s'))) {
        throw const FormatException('Connection info contains an invalid HTTPS address, fingerprint, or token.');
      }
      return PiConnectionHandoff(
        apiBaseUrl: apiBaseUrl,
        serverCertSha256: PiCertificatePin.normalize(pin),
        apiToken: token,
      );
    } on FormatException {
      rethrow;
    } on Object {
      throw const FormatException('Connection info is not valid UTF-8 JSON.');
    }
  }
}

class WifiProvisioningClient {
  static const serviceUuid = '8c6d0001-7a4b-4f61-b7a5-927f4e2a1000';
  static const credentialsUuid = '8c6d0002-7a4b-4f61-b7a5-927f4e2a1000';
  static const statusUuid = '8c6d0003-7a4b-4f61-b7a5-927f4e2a1000';
  static const connectionInfoUuid = '8c6d0004-7a4b-4f61-b7a5-927f4e2a1000';

  Future<PiConnectionHandoff> provision({
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
      await device.connect(license: License.free);
      final services = await device.discoverServices();
      final service = _firstOrNull(
        services.where(
          (entry) => entry.uuid.toString().toLowerCase() == serviceUuid,
        ),
      );
      if (service == null) {
        throw StateError('The Thashu setup service was not found.');
      }
      final credentials = _characteristic(service, credentialsUuid);
      final status = _characteristic(service, statusUuid);
      final connectionInfo = _characteristic(service, connectionInfoUuid);
      if (credentials == null || status == null || connectionInfo == null) {
        throw StateError('The Thashu setup characteristics are incomplete.');
      }

      var currentStatus = await _readStatus(status);
      if (currentStatus == 'expired' || currentStatus == 'invalid') {
        throw StateError('The Pi setup window expired. Hold its button for 3 seconds and retry.');
      }
      final payload = utf8.encode(jsonEncode({'ssid': ssid, 'password': password}));
      // The Pi requires an encrypted reliable GATT write. Android/iOS perform
      // link encryption when the protected characteristic is accessed.
      await credentials.write(payload, withoutResponse: false, allowLongWrite: true);

      // The Pi's physical-button window lasts 60 seconds. Do not retry the
      // one-time connection-info read: a successful read consumes the handoff.
      final deadline = DateTime.now().add(const Duration(seconds: 60));
      while (DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(seconds: 2));
        currentStatus = await _readStatus(status);
        switch (currentStatus) {
          case 'connected':
            return PiConnectionHandoff.fromBytes(await connectionInfo.read());
          case 'failed':
            throw StateError('The Pi could not join that hotspot. Check its SSID, password, and WPA2 setting.');
          case 'invalid':
          case 'expired':
            throw StateError('The Pi setup window expired. Hold its button for 3 seconds and retry.');
          case 'idle':
            throw StateError('The Pi setup window is not active. Hold its button for 3 seconds and retry.');
          case 'waiting':
          case 'received':
          case 'connecting':
            break;
          default:
            throw StateError('The Pi returned an unrecognized setup status.');
        }
      }
      throw StateError('The Pi did not finish joining the hotspot within the setup window.');
    } finally {
      await FlutterBluePlus.stopScan();
      await scanSubscription?.cancel();
      if (device != null && device.isConnected) {
        await device.disconnect();
      }
    }
  }

  BluetoothCharacteristic? _characteristic(
    BluetoothService service,
    String uuid,
  ) =>
      _firstOrNull(
        service.characteristics.where(
          (entry) => entry.uuid.toString().toLowerCase() == uuid,
        ),
      );

  Future<String> _readStatus(BluetoothCharacteristic status) async {
    final value = utf8.decode(await status.read()).trim().toLowerCase();
    const allowed = {
      'idle',
      'waiting',
      'received',
      'connecting',
      'connected',
      'failed',
      'invalid',
      'expired',
    };
    if (!allowed.contains(value)) {
      throw StateError('The Pi returned an unrecognized setup status.');
    }
    return value;
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
