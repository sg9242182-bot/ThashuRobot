import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'pinned_pi_tls.dart';

/// Stores the Pi origin, token, and optional leaf-certificate pin securely.
class PiConnectionSettings {
  PiConnectionSettings({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _addressKey = 'pi_api_base_url';
  static const _tokenKey = 'pi_api_bearer_token';
  static const _certificatePinKey = 'pi_api_certificate_sha256';

  final FlutterSecureStorage _storage;

  Future<String?> readAddress() => _storage.read(key: _addressKey);

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<String?> readCertificatePin() =>
      _storage.read(key: _certificatePinKey);

  Future<void> save({
    required String baseUrl,
    String? bearerToken,
    String? certificateSha256Fingerprint,
  }) async {
    final normalized = baseUrl.trim().replaceFirst(RegExp(r'/+$'), '');
    final uri = Uri.tryParse(normalized);
    if (uri == null ||
        !uri.hasAuthority ||
        uri.scheme != 'https' ||
        uri.userInfo.isNotEmpty ||
        uri.path.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw ArgumentError.value(
        baseUrl,
        'baseUrl',
        'Enter the HTTPS Pi origin, for example https://192.168.1.42:8443.',
      );
    }

    final providedPin = certificateSha256Fingerprint?.trim();
    if (uri.port == 8443 && (providedPin == null || providedPin.isEmpty)) {
      throw ArgumentError.value(
        certificateSha256Fingerprint,
        'certificateSha256Fingerprint',
        'The Pi local HTTPS connection requires its SHA-256 certificate fingerprint.',
      );
    }
    final pin = providedPin == null || providedPin.isEmpty
        ? null
        : PiCertificatePin.normalize(providedPin);

    await _storage.write(key: _addressKey, value: normalized);
    final token = bearerToken?.trim();
    if (token != null && token.isNotEmpty) {
      await _storage.write(key: _tokenKey, value: token);
    }
    if (pin == null) {
      await _storage.delete(key: _certificatePinKey);
    } else {
      await _storage.write(key: _certificatePinKey, value: pin);
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _addressKey);
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _certificatePinKey);
  }
}
