import 'dart:async';
import 'dart:io';

import '../core/pi_api_exception.dart';
import '../models/telemetry_event.dart';

enum TelemetryConnectionState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  failed,
}

abstract interface class PiTelemetrySocket {
  Stream<Object?> get messages;

  Future<void> close();
}

abstract interface class PiTelemetryTransport {
  Future<PiTelemetrySocket> connect(
    Uri uri, {
    required Map<String, String> headers,
  });
}

class IoPiTelemetryTransport implements PiTelemetryTransport {
  @override
  Future<PiTelemetrySocket> connect(
    Uri uri, {
    required Map<String, String> headers,
  }) async {
    final socket = await WebSocket.connect(uri.toString(), headers: headers);
    return _IoPiTelemetrySocket(socket);
  }
}

class _IoPiTelemetrySocket implements PiTelemetrySocket {
  const _IoPiTelemetrySocket(this._socket);

  final WebSocket _socket;

  @override
  Stream<Object?> get messages => _socket;

  @override
  Future<void> close() async {
    await _socket.close();
  }
}

/// Flutter client for the currently documented Pi telemetry WebSocket.
///
/// Reconnection is explicit: retry timing has not been agreed with the API
/// owner, so this client never starts an unbounded or guessed retry loop.
class PiTelemetryClient {
  PiTelemetryClient({
    required Uri baseUri,
    required String? bearerToken,
    PiTelemetryTransport? transport,
  }) : _baseUri = _validateBaseUri(baseUri),
       // Keep the token parameter public without exposing the stored token.
       // ignore: prefer_initializing_formals
       _bearerToken = bearerToken,
       _transport = transport ?? IoPiTelemetryTransport();

  final Uri _baseUri;
  final String? _bearerToken;
  final PiTelemetryTransport _transport;
  final StreamController<TelemetryConnectionState> _states =
      StreamController<TelemetryConnectionState>.broadcast();
  final StreamController<TelemetryEvent> _events =
      StreamController<TelemetryEvent>.broadcast();

  TelemetryConnectionState _state = TelemetryConnectionState.disconnected;
  TelemetryConnectionState get state => _state;
  Stream<TelemetryConnectionState> get states => _states.stream;
  Stream<TelemetryEvent> get events => _events.stream;
  Object? lastError;
  TelemetryEvent? latestEvent;
  SensorTelemetryFrame? latestSensorFrame;
  DateTime? latestSensorFrameReceivedAt;
  DateTime? latestSensorPiReceivedAt;
  int _connectionGeneration = 0;
  int? _latestEventGeneration;
  bool get hasCurrentConnectionEvent =>
      _state == TelemetryConnectionState.connected &&
      latestEvent != null &&
      _latestEventGeneration == _connectionGeneration;

  PiTelemetrySocket? _socket;
  StreamSubscription<Object?>? _subscription;
  bool _disposed = false;
  bool _hasConnected = false;

  Uri get telemetryUri {
    final httpUri = _baseUri.resolve('/api/v1/telemetry');
    return httpUri.replace(scheme: httpUri.scheme == 'https' ? 'wss' : 'ws');
  }

  Future<void> connect() async {
    if (_disposed) throw StateError('PiTelemetryClient is disposed.');
    if (_state == TelemetryConnectionState.connecting ||
        _state == TelemetryConnectionState.reconnecting ||
        _state == TelemetryConnectionState.connected) {
      return;
    }

    final token = _bearerToken?.trim();
    if (token == null || token.isEmpty) {
      lastError = const PiApiException(
        code: 'credentials_not_configured',
        message: 'A Pi Bearer token is required for telemetry.',
      );
      _setState(TelemetryConnectionState.failed);
      return;
    }

    lastError = null;
    _setState(
      _hasConnected
          ? TelemetryConnectionState.reconnecting
          : TelemetryConnectionState.connecting,
    );
    try {
      await _closeCurrentSocket();
      if (_disposed) return;

      final socket = await _transport.connect(
        telemetryUri,
        headers: {'Authorization': 'Bearer $token'},
      );
      if (_disposed) {
        await socket.close();
        return;
      }

      _socket = socket;
      _hasConnected = true;
      _connectionGeneration++;
      _setState(TelemetryConnectionState.connected);
      _subscription = socket.messages.listen(
        (frame) {
          final event = parseTelemetryEvent(frame);
          latestEvent = event;
          if (event is Esp32LineEvent && event.sensorFrame != null) {
            latestSensorFrame = event.sensorFrame;
            latestSensorFrameReceivedAt = DateTime.now();
            latestSensorPiReceivedAt = event.receivedAt;
          }
          _latestEventGeneration = _connectionGeneration;
          if (!_events.isClosed) _events.add(event);
        },
        onError: (Object error) {
          lastError = error;
          _setState(TelemetryConnectionState.failed);
        },
        onDone: () {
          _socket = null;
          _subscription = null;
          _setState(TelemetryConnectionState.disconnected);
        },
        cancelOnError: false,
      );
    } catch (error) {
      lastError = error;
      _setState(TelemetryConnectionState.failed);
    }
  }

  Future<void> disconnect() async {
    await _closeCurrentSocket();
    _setState(TelemetryConnectionState.disconnected);
  }

  Future<void> _closeCurrentSocket() async {
    final socket = _socket;
    _socket = null;
    final subscription = _subscription;
    _subscription = null;
    await subscription?.cancel();
    await socket?.close();
  }

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    await disconnect();
    unawaited(_states.close());
    unawaited(_events.close());
  }

  void _setState(TelemetryConnectionState next) {
    if (_state == next) return;
    _state = next;
    if (!_states.isClosed) _states.add(next);
  }

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
}
