import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/services/pinned_pi_tls.dart';

void main() {
  const sha256Abc =
      'sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

  test('normalizes and compares the exact SHA-256 DER fingerprint', () {
    expect(
      PiCertificatePin.normalize(
        ' BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD ',
      ),
      sha256Abc,
    );
    expect(PiCertificatePin.fingerprintForDer('abc'.codeUnits), sha256Abc);
    expect(PiCertificatePin.matchesDer('abc'.codeUnits, sha256Abc), isTrue);
    expect(PiCertificatePin.matchesDer('abd'.codeUnits, sha256Abc), isFalse);
  });

  test('rejects malformed pins and HTTP origins', () {
    expect(() => PiCertificatePin.normalize('bad'), throwsFormatException);
    expect(
      () => createPiTlsClient(
        origin: Uri.parse('http://192.168.1.42:8443'),
        certificateSha256Fingerprint: sha256Abc,
      ),
      throwsArgumentError,
    );
  });

  test('creates a pinned HTTPS client without accepting all certificates', () {
    final client = createPiTlsClient(
      origin: Uri.parse('https://192.168.1.42:8443'),
      certificateSha256Fingerprint: sha256Abc,
    );
    addTearDown(() => client.close(force: true));
    expect(client, isA<HttpClient>());
  });
}
