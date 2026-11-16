import 'dart:io';

import 'package:crypto/crypto.dart';

/// SHA-256 leaf-certificate pinning for the Pi's local HTTPS/WSS listener.
class PiCertificatePin {
  static String normalize(String value) {
    final normalized = value.trim().toLowerCase();
    final digest = normalized.startsWith('sha256:')
        ? normalized.substring('sha256:'.length)
        : normalized;
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(digest)) {
      throw const FormatException(
        'Certificate fingerprint must be SHA-256 (64 hexadecimal characters).',
      );
    }
    return 'sha256:$digest';
  }

  static String fingerprintForDer(List<int> certificateDer) =>
      'sha256:${sha256.convert(certificateDer)}';

  static bool matchesDer(List<int> certificateDer, String expected) =>
      fingerprintForDer(certificateDer) == normalize(expected);
}

/// Uses normal platform trust when no pin is configured. With a pin, the
/// exact leaf certificate and origin host/port must match; no global bypass.
HttpClient createPiTlsClient({
  required Uri origin,
  String? certificateSha256Fingerprint,
}) {
  final fingerprint = certificateSha256Fingerprint;
  if (fingerprint == null || fingerprint.trim().isEmpty) return HttpClient();
  if (origin.scheme != 'https') {
    throw ArgumentError.value(
      origin,
      'origin',
      'A certificate pin requires an HTTPS/WSS origin.',
    );
  }

  final pin = PiCertificatePin.normalize(fingerprint);
  final client = HttpClient(context: SecurityContext(withTrustedRoots: false));
  client.findProxy = (_) => 'DIRECT';
  client.badCertificateCallback = (certificate, host, port) =>
      host == origin.host &&
      port == origin.port &&
      PiCertificatePin.matchesDer(certificate.der, pin);
  return client;
}
