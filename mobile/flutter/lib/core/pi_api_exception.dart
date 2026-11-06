/// A translated Pi API error or local client-side request validation error.
class PiApiException implements Exception {
  const PiApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.details,
  });

  final String code;
  final String message;
  final int? statusCode;
  final Object? details;

  @override
  String toString() => 'PiApiException($code): $message';
}
