import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Stores the Pi origin and API Bearer token in platform secure storage.
class PiConnectionSettings {
  PiConnectionSettings({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _addressKey = 'pi_api_base_url';
  static const _tokenKey = 'pi_api_bearer_token';

  final FlutterSecureStorage _storage;

  Future<String?> readAddress() => _storage.read(key: _addressKey);

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<void> save({
    required String baseUrl,
    String? bearerToken,
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
        'Enter the HTTPS Pi origin, such as https://thashu.local:8000.',
      );
    }

    await _storage.write(key: _addressKey, value: normalized);
    final token = bearerToken?.trim();
    if (token != null && token.isNotEmpty) {
      await _storage.write(key: _tokenKey, value: token);
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _addressKey);
    await _storage.delete(key: _tokenKey);
  }
}
