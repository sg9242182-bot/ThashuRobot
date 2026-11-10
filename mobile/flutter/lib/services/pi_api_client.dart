import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../core/pi_api_exception.dart';
import '../models/pi_health.dart';
import '../models/pi_status.dart';
import '../models/robot_command.dart';
import '../models/robot_mode.dart';
import '../models/robot_move_request.dart';
import '../models/robot_move_validator.dart';
import 'pinned_pi_tls.dart';

class PiApiHttpResponse {
  const PiApiHttpResponse({
    required this.statusCode,
    required this.body,
    this.headers = const {},
  });

  final int statusCode;
  final String body;
  final Map<String, String> headers;
}

/// Small injectable boundary so client behavior can be tested without a Pi.
abstract interface class PiApiTransport {
  Future<PiApiHttpResponse> get(
    Uri uri, {
    required Map<String, String> headers,
  });

  Future<PiApiHttpResponse> post(
    Uri uri, {
    required Map<String, String> headers,
    Object? jsonBody,
  });

  void close();
}

class IoPiApiTransport implements PiApiTransport {
  IoPiApiTransport({
    required Uri origin,
    String? certificateSha256Fingerprint,
    HttpClient? httpClient,
  }) : _httpClient = httpClient ??
           createPiTlsClient(
             origin: origin,
             certificateSha256Fingerprint: certificateSha256Fingerprint,
           );

  final HttpClient _httpClient;

  @override
  Future<PiApiHttpResponse> get(
    Uri uri, {
    required Map<String, String> headers,
  }) => _send('GET', uri, headers: headers);

  @override
  Future<PiApiHttpResponse> post(
    Uri uri, {
    required Map<String, String> headers,
    Object? jsonBody,
  }) => _send('POST', uri, headers: headers, jsonBody: jsonBody);

  Future<PiApiHttpResponse> _send(
    String method,
    Uri uri, {
    required Map<String, String> headers,
    Object? jsonBody,
  }) async {
    final request = await _httpClient.openUrl(method, uri);
    headers.forEach(request.headers.set);
    if (jsonBody != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(jsonBody));
    }

    final response = await request.close();
    final body = await utf8.decoder.bind(response).join();
    final responseHeaders = <String, String>{};
    response.headers.forEach((name, values) {
      responseHeaders[name.toLowerCase()] = values.join(',');
    });
    return PiApiHttpResponse(
      statusCode: response.statusCode,
      body: body,
      headers: Map.unmodifiable(responseHeaders),
    );
  }

  @override
  void close() => _httpClient.close(force: true);
}

/// REST client for routes and JSON fields currently confirmed by Vishal.
///
/// Pass the Pi's root URL and configured Bearer token when they are available.
/// No Pi address or credential is guessed or stored in the app.
class PiApiClient {
  PiApiClient({
    required Uri baseUri,
    // Keep the parameter public and the stored token private.
    String? bearerToken,
    String? certificateSha256Fingerprint,
    PiApiTransport? transport,
    this.requestTimeout = const Duration(seconds: 5),
  }) : _baseUri = _validateBaseUri(baseUri),
       // ignore: prefer_initializing_formals
       _bearerToken = bearerToken,
       _transport = transport ?? IoPiApiTransport();

  final Uri _baseUri;
  final String? _bearerToken;
  final String? _certificateSha256Fingerprint;
  final PiApiTransport _transport;
  final Duration requestTimeout;
  Future<RobotCommandResult>? _moveInFlight;
  RobotMoveRequest? _moveInFlightRequest;
  String? _moveInFlightMode;
  Future<RobotCommandResult>? _stopInFlight;
  String? _stopInFlightRequestId;

  static Uri _validateBaseUri(Uri uri) {
    if (!uri.hasAuthority ||
        (uri.scheme != 'http' && uri.scheme != 'https') ||
        uri.userInfo.isNotEmpty) {
      throw ArgumentError.value(
        uri,
        'baseUri',
        'Use an HTTP(S) Pi origin, for example http://host:8000.',
      );
    }
    return uri;
  }

  static String? _validateCertificatePin(Uri uri, String? value) {
    final pin = value?.trim();
    if (uri.port == 8443 && (pin == null || pin.isEmpty)) {
      throw ArgumentError.value(
        value,
        'certificateSha256Fingerprint',
        'The Pi local HTTPS listener requires its certificate fingerprint.',
      );
    }
    if (pin == null || pin.isEmpty) return null;
    if (uri.scheme != 'https') {
      throw ArgumentError.value(value, 'certificateSha256Fingerprint', 'A certificate pin requires HTTPS.');
    }
    return PiCertificatePin.normalize(pin);
  }

  Uri _endpoint(String path) => _baseUri.resolve(path);

  Map<String, String> _headers({bool authenticated = false}) {
    final headers = <String, String>{'Accept': 'application/json'};
    if (authenticated) {
      final token = _bearerToken?.trim();
      if (token == null || token.isEmpty) {
        throw const PiApiException(
          code: 'credentials_not_configured',
          message: 'A Pi Bearer token is required for this operation.',
        );
      }
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<PiStatus> getStatus() => _getJson(
    '/api/v1/status',
    authenticated: false,
    parser: PiStatus.fromJson,
  );

  /// Checks API liveness only; this does not confirm robot or ESP32 readiness.
  Future<PiHealth> getHealth() =>
      _getJson('/health', authenticated: false, parser: PiHealth.fromJson);

  Future<RobotModeResponse> setMode(RobotMode mode) => _postJson(
    '/api/v1/robot/mode',
    mode.toRequestJson(),
    authenticated: true,
    parser: RobotModeResponse.fromJson,
  );

  /// Reuses [request.requestId] when retrying the same move action.
  Future<RobotCommandResult> move(
    RobotMoveRequest request, {
    required String controlMode,
  }) async {
    _validateRequestId(request.requestId);
    final validationError = RobotMoveValidator.validate(
      controlMode: controlMode,
      direction: request.direction,
      speed: request.speed,
    );
    if (validationError != null) {
      final message = switch (validationError) {
        RobotMoveValidationError.manualModeRequired =>
          'Switch the robot to MANUAL mode before moving.',
        RobotMoveValidationError.unsupportedDirection =>
          'Choose forward, backward, left, or right.',
        RobotMoveValidationError.speedOutOfRange =>
          'Speed must be an integer from 0 to 255.',
      };
      throw PiApiException(
        code: 'invalid_move_request',
        message: message,
        details: validationError.name,
      );
    }

    if (_stopInFlight != null) {
      throw const PiApiException(
        code: 'command_in_progress',
        message: 'Wait for the STOP request to finish before moving.',
      );
    }

    final activeMove = _moveInFlight;
    if (activeMove != null) {
      final activeRequest = _moveInFlightRequest!;
      final sameAction =
          activeRequest.requestId == request.requestId &&
          activeRequest.direction == request.direction &&
          activeRequest.speed == request.speed &&
          _moveInFlightMode == controlMode;
      if (sameAction) return activeMove;
      throw const PiApiException(
        code: 'command_in_progress',
        message: 'Wait for the current move request to finish.',
      );
    }

    final requestFuture = _postJson(
      '/api/v1/robot/move',
      request.toJson(),
      authenticated: true,
      parser: RobotCommandResult.fromJson,
    );
    _moveInFlight = requestFuture;
    _moveInFlightRequest = request;
    _moveInFlightMode = controlMode;
    try {
      return await requestFuture;
    } finally {
      if (identical(_moveInFlight, requestFuture)) {
        _moveInFlight = null;
        _moveInFlightRequest = null;
        _moveInFlightMode = null;
      }
    }
  }

  /// Reuses [requestId] for concurrent retries of the same STOP action.
  /// A new STOP press must use a new UUID to send a fresh command.
  Future<RobotCommandResult> stop({required String requestId}) async {
    _validateRequestId(requestId);
    final activeStop = _stopInFlight;
    if (activeStop != null) {
      if (_stopInFlightRequestId == requestId) return activeStop;
      throw const PiApiException(
        code: 'command_in_progress',
        message: 'Wait for the current STOP request to finish.',
      );
    }

    final requestFuture = _postJson(
      '/api/v1/robot/stop',
      {'request_id': requestId},
      authenticated: true,
      parser: RobotCommandResult.fromJson,
    );
    _stopInFlight = requestFuture;
    _stopInFlightRequestId = requestId;
    try {
      return await requestFuture;
    } finally {
      if (identical(_stopInFlight, requestFuture)) {
        _stopInFlight = null;
        _stopInFlightRequestId = null;
      }
    }
  }

  static void _validateRequestId(String value) {
    if (!RobotRequestId.isValid(value)) {
      throw ArgumentError.value(
        value,
        'requestId',
        'Must be a UUID. Keep the same ID when retrying an action.',
      );
    }
  }

  Future<RobotCommandResult> getCommand(String commandId) {
    final id = commandId.trim();
    if (id.isEmpty) {
      throw ArgumentError.value(commandId, 'commandId', 'Must not be empty.');
    }
    return _getJson(
      '/api/v1/robot/commands/${Uri.encodeComponent(id)}',
      authenticated: true,
      parser: RobotCommandResult.fromJson,
    );
  }

  Future<T> _getJson<T>(
    String path, {
    required bool authenticated,
    required T Function(Map<String, dynamic>) parser,
  }) async {
    final headers = _headers(authenticated: authenticated);
    return _sendAndParse(
      () => _transport.get(_endpoint(path), headers: headers),
      parser,
    );
  }

  Future<T> _postJson<T>(
    String path,
    Object? body, {
    required bool authenticated,
    required T Function(Map<String, dynamic>) parser,
  }) async {
    final headers = _headers(authenticated: authenticated);
    return _sendAndParse(
      () => _transport.post(_endpoint(path), headers: headers, jsonBody: body),
      parser,
    );
  }

  Future<T> _sendAndParse<T>(
    Future<PiApiHttpResponse> Function() send,
    T Function(Map<String, dynamic>) parser,
  ) async {
    late final PiApiHttpResponse response;
    try {
      response = await send().timeout(requestTimeout);
    } on TimeoutException {
      throw const PiApiException(
        code: 'timeout',
        message: 'The Pi API request timed out.',
      );
    } on SocketException catch (error) {
      throw PiApiException(code: 'unreachable', message: error.message);
    } on HttpException catch (error) {
      throw PiApiException(code: 'connection_error', message: error.message);
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _httpError(response);
    }

    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Expected a JSON object response.');
      }
      return parser(decoded);
    } on FormatException catch (error) {
      throw PiApiException(code: 'malformed_response', message: error.message);
    }
  }

  PiApiException _httpError(PiApiHttpResponse response) {
    Object? details;
    Map<String, dynamic>? detailMap;
    String message = 'The Pi API returned HTTP ${response.statusCode}.';
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic> && decoded.containsKey('detail')) {
        details = decoded['detail'];
        if (details is Map<String, dynamic>) detailMap = details;
        message = details is String ? details : jsonEncode(details);
      }
    } on FormatException {
      if (response.body.isNotEmpty) message = response.body;
    }

    final backendCode = detailMap?['error_code'] is String
        ? detailMap!['error_code'] as String
        : null;
    final retryAfter = _retryAfter(response.headers, detailMap);
    final retryable =
        detailMap?['retryable'] == true || response.statusCode == 429;
    final code = switch (response.statusCode) {
      401 => 'unauthorized',
      404 => 'command_not_found',
      409 => 'conflict',
      413 => 'payload_too_large',
      415 => 'unsupported_media_type',
      422 => 'invalid_input',
      429 => 'rate_limited',
      503 when backendCode == 'API_BUSY' => 'api_busy',
      503 when backendCode == 'ROBOT_UNAVAILABLE' => 'robot_unavailable',
      503 => 'service_unavailable',
      >= 500 => 'server_error',
      _ => 'request_failed',
    };

    if (code == 'rate_limited') {
      final delay = retryAfter == null
          ? ' Try again shortly.'
          : ' Try again in ${_formatSeconds(retryAfter)} seconds.';
      message = 'The Pi rate limit was reached. No command was sent.$delay';
    } else if (code == 'api_busy') {
      message = 'The Pi command queue is busy. This request was not sent; retry shortly.';
    }

    return PiApiException(
      code: code,
      message: message,
      statusCode: response.statusCode,
      details: details,
      backendCode: backendCode,
      retryAfter: retryAfter,
      retryable: retryable,
    );
  }

  Duration? _retryAfter(
    Map<String, String> headers,
    Map<String, dynamic>? details,
  ) {
    final seconds = details?['retry_after_seconds'];
    if (seconds is num && seconds.isFinite && seconds >= 0) {
      return Duration(
        microseconds: (seconds * Duration.microsecondsPerSecond).round(),
      );
    }

    String? header;
    for (final entry in headers.entries) {
      if (entry.key.toLowerCase() == 'retry-after') {
        header = entry.value;
        break;
      }
    }
    if (header == null) return null;

    final numericSeconds = double.tryParse(header.trim());
    if (numericSeconds != null &&
        numericSeconds.isFinite &&
        numericSeconds >= 0) {
      return Duration(
        microseconds: (numericSeconds * Duration.microsecondsPerSecond).round(),
      );
    }
    try {
      final retryAt = HttpDate.parse(header);
      final delay = retryAt.difference(DateTime.now().toUtc());
      return delay.isNegative ? Duration.zero : delay;
    } on FormatException {
      return null;
    }
  }

  String _formatSeconds(Duration duration) {
    final seconds = duration.inMicroseconds / Duration.microsecondsPerSecond;
    return seconds.toStringAsFixed(seconds < 1 ? 1 : 0);
  }

  void close() => _transport.close();
}
