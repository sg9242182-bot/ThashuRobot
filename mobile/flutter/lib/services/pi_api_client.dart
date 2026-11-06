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

class PiApiHttpResponse {
  const PiApiHttpResponse({required this.statusCode, required this.body});

  final int statusCode;
  final String body;
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
  IoPiApiTransport({HttpClient? httpClient})
    : _httpClient = httpClient ?? HttpClient();

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
    return PiApiHttpResponse(statusCode: response.statusCode, body: body);
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
    PiApiTransport? transport,
    this.requestTimeout = const Duration(seconds: 5),
  }) : _baseUri = _validateBaseUri(baseUri),
       // ignore: prefer_initializing_formals
       _bearerToken = bearerToken,
       _transport = transport ?? IoPiApiTransport();

  final Uri _baseUri;
  final String? _bearerToken;
  final PiApiTransport _transport;
  final Duration requestTimeout;
  Future<RobotCommandResult>? _moveInFlight;
  RobotMoveRequest? _moveInFlightRequest;
  String? _moveInFlightMode;
  final Map<String, Future<RobotCommandResult>> _stopRequestsInFlight = {};

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

    if (_stopRequestsInFlight.isNotEmpty) {
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

  /// A fresh STOP press needs a fresh ID; retries of that press reuse it.
  Future<RobotCommandResult> stop({required String requestId}) async {
    _validateRequestId(requestId);
    final activeStop = _stopRequestsInFlight[requestId];
    if (activeStop != null) return activeStop;

    final requestFuture = _postJson(
      '/api/v1/robot/stop',
      {'request_id': requestId},
      authenticated: true,
      parser: RobotCommandResult.fromJson,
    );
    _stopRequestsInFlight[requestId] = requestFuture;
    try {
      return await requestFuture;
    } finally {
      if (identical(_stopRequestsInFlight[requestId], requestFuture)) {
        _stopRequestsInFlight.remove(requestId);
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
    String message = 'The Pi API returned HTTP ${response.statusCode}.';
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic> && decoded.containsKey('detail')) {
        details = decoded['detail'];
        message = details is String ? details : jsonEncode(details);
      }
    } on FormatException {
      if (response.body.isNotEmpty) message = response.body;
    }

    final code = switch (response.statusCode) {
      401 => 'unauthorized',
      404 => 'command_not_found',
      409 => 'conflict',
      422 => 'invalid_input',
      413 => 'payload_too_large',
      503 => 'service_unavailable',
      >= 500 => 'server_error',
      _ => 'request_failed',
    };
    return PiApiException(
      code: code,
      message: message,
      statusCode: response.statusCode,
      details: details,
    );
  }

  void close() => _transport.close();
}
