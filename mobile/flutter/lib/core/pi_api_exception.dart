/// A translated Pi API error or local client-side request validation error.
class PiApiException implements Exception {
  const PiApiException({
    required this.code,
    required this.message,
    this.statusCode,
    this.details,
    this.backendCode,
    this.retryAfter,
    this.retryable = false,
  });

  /// Stable Flutter-facing error category.
  final String code;
  final String message;
  final int? statusCode;
  final Object? details;

  /// Stable machine-readable error code returned by the Pi, when available.
  final String? backendCode;

  /// Server-provided delay before the caller should retry, when available.
  final Duration? retryAfter;

  /// Whether the Pi explicitly says this request can be retried.
  final bool retryable;

  @override
  String toString() => 'PiApiException($code): $message';
}
