import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/services/wifi_provisioning_client.dart';

void main() {
  const fingerprint =
      '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

  test('parses the exact UTF-8 BLE connection-info payload', () {
    final handoff = PiConnectionHandoff.fromBytes(
      utf8.encode(
        '{"api_base_url":"https://192.168.1.42:8443",'
        '"server_cert_sha256":"$fingerprint","api_token":"secret-test-token"}',
      ),
    );

    expect(handoff.apiBaseUrl, 'https://192.168.1.42:8443');
    expect(handoff.serverCertSha256, 'sha256:$fingerprint');
    expect(handoff.apiToken, 'secret-test-token');
  });

  test('rejects missing, extra, or wrongly typed fields', () {
    for (final json in [
      '{"api_base_url":"https://192.168.1.42:8443",'
          '"server_cert_sha256":"$fingerprint"}',
      '{"api_base_url":"https://192.168.1.42:8443",'
          '"server_cert_sha256":"$fingerprint","api_token":"token","extra":1}',
      '{"api_base_url":42,"server_cert_sha256":"$fingerprint","api_token":"token"}',
    ]) {
      expect(
        () => PiConnectionHandoff.fromBytes(utf8.encode(json)),
        throwsFormatException,
      );
    }
  });

  test('rejects invalid URL, pin, and token values', () {
    for (final url in [
      'http://192.168.1.42:8443',
      'https://thashu.local:8443',
      'https://192.168.1.42:8000',
      'https://192.168.1.42:8443/api',
    ]) {
      final json =
          '{"api_base_url":"$url","server_cert_sha256":"$fingerprint",'
          '"api_token":"token"}';
      expect(
        () => PiConnectionHandoff.fromBytes(utf8.encode(json)),
        throwsFormatException,
      );
    }
    final colonPin =
        '{"api_base_url":"https://192.168.1.42:8443",'
        '"server_cert_sha256":"01:23","api_token":"token"}';
    expect(
      () => PiConnectionHandoff.fromBytes(utf8.encode(colonPin)),
      throwsFormatException,
    );
    final emptyToken =
        '{"api_base_url":"https://192.168.1.42:8443",'
        '"server_cert_sha256":"$fingerprint","api_token":""}';
    expect(
      () => PiConnectionHandoff.fromBytes(utf8.encode(emptyToken)),
      throwsFormatException,
    );
  });
}
