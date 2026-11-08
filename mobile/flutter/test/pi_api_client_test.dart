import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:thashu_app/core/pi_api_exception.dart';
import 'package:thashu_app/models/robot_mode.dart';
import 'package:thashu_app/models/robot_move_request.dart';
import 'package:thashu_app/services/pi_api_client.dart';

void main() {
  group('PiApiClient', () {
    late _FakeTransport transport;
    late PiApiClient client;

    setUp(() {
      transport = _FakeTransport();
      client = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        bearerToken: 'test-token',
        transport: transport,
      );
    });

    test('checks API liveness without a bearer token', () async {
      transport.responses.add(
        const PiApiHttpResponse(statusCode: 200, body: '{"status":"ok"}'),
      );

      final health = await client.getHealth();

      expect(transport.lastUri!.path, '/health');
      expect(transport.lastHeaders, {'Accept': 'application/json'});
      expect(health.status, 'ok');
    });

    test(
      'parses the currently documented status without authentication',
      () async {
        transport.responses.add(
          const PiApiHttpResponse(
            statusCode: 200,
            body:
                '{"api":"ok","esp32_transport":"connected",'
                '"control_mode":"AUTO","controller_readiness":"unknown"}',
          ),
        );

        final status = await client.getStatus();

        expect(transport.lastUri!.path, '/api/v1/status');
        expect(transport.lastHeaders, {'Accept': 'application/json'});
        expect(status.api, 'ok');
        expect(status.esp32Transport, 'connected');
        expect(status.controlMode, 'AUTO');
        expect(status.controllerReadiness, 'unknown');
      },
    );

    test('sends the confirmed mode request with the bearer token', () async {
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 200,
          body: '{"mode":"MANUAL","status":"switched"}',
        ),
      );

      final response = await client.setMode(RobotMode.manual);

      expect(transport.lastUri!.path, '/api/v1/robot/mode');
      expect(transport.lastJsonBody, {'mode': 'MANUAL'});
      expect(transport.lastHeaders!['Authorization'], 'Bearer test-token');
      expect(response.mode, 'MANUAL');
      expect(response.status, 'switched');
    });

    test(
      'sends a move with the required retry ID and confirmed fields',
      () async {
        transport.responses.add(
          const PiApiHttpResponse(
            statusCode: 202,
            body:
                '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
                '"command_id":"cmd-1","command":"forward",'
                '"status":"dispatched","control_mode":"MANUAL",'
                '"error_code":null,"timestamp":"2026-11-05T12:00:00Z"}',
          ),
        );

        final request = RobotMoveRequest(
          requestId: 'b1234567-89ab-4cde-8f01-23456789abcd',
          direction: 'forward',
          speed: 200,
        );
        final response = await client.move(request, controlMode: 'MANUAL');

        expect(transport.lastUri!.path, '/api/v1/robot/move');
        expect(transport.lastJsonBody, {
          'request_id': request.requestId,
          'direction': 'forward',
          'speed': 200,
        });
        expect(transport.lastHeaders!['Authorization'], 'Bearer test-token');
        expect(response.requestId, request.requestId);
        expect(response.command, 'forward');
        expect(response.status, 'dispatched');
      },
    );

    test('blocks a move locally unless mode and fields are valid', () async {
      final request = RobotMoveRequest(
        requestId: 'b1234567-89ab-4cde-8f01-23456789abcd',
        direction: 'forward',
        speed: 200,
      );

      await expectLater(
        client.move(request, controlMode: 'AUTO'),
        throwsA(
          isA<PiApiException>()
              .having((error) => error.code, 'code', 'invalid_move_request')
              .having(
                (error) => error.details,
                'details',
                'manualModeRequired',
              ),
        ),
      );
      expect(transport.lastUri, isNull);

      final invalidSpeed = RobotMoveRequest(
        requestId: 'c1234567-89ab-4cde-8f01-23456789abcd',
        direction: 'forward',
        speed: 256,
      );
      await expectLater(
        client.move(invalidSpeed, controlMode: 'MANUAL'),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.details,
            'details',
            'speedOutOfRange',
          ),
        ),
      );
      expect(transport.lastUri, isNull);
    });

    test('sends STOP with a retry ID on the confirmed route', () async {
      const requestId = 'c1234567-89ab-4cde-8f01-23456789abcd';
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"c1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-stop","command":"stop",'
              '"status":"dispatched","control_mode":"AUTO",'
              '"error_code":null,"timestamp":"2026-11-05T12:00:00Z"}',
        ),
      );

      final response = await client.stop(requestId: requestId);

      expect(transport.lastUri!.path, '/api/v1/robot/stop');
      expect(transport.lastJsonBody, {'request_id': requestId});
      expect(response.requestId, requestId);
      expect(response.command, 'stop');
    });

    test('coalesces simultaneous retries of the same move request', () async {
      final responseCompleter = Completer<PiApiHttpResponse>();
      transport.postCompleter = responseCompleter;
      const requestId = 'b1234567-89ab-4cde-8f01-23456789abcd';
      final request = RobotMoveRequest(
        requestId: requestId,
        direction: 'forward',
        speed: 200,
      );

      final first = client.move(request, controlMode: 'MANUAL');
      final retry = client.move(request, controlMode: 'MANUAL');

      expect(transport.postCount, 1);
      responseCompleter.complete(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"dispatched","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-05T12:00:00Z"}',
        ),
      );

      expect((await first).commandId, (await retry).commandId);
      expect(transport.postCount, 1);
    });

    test('blocks a different move while a move request is in flight', () async {
      final responseCompleter = Completer<PiApiHttpResponse>();
      transport.postCompleter = responseCompleter;
      final first = client.move(
        RobotMoveRequest(
          requestId: 'b1234567-89ab-4cde-8f01-23456789abcd',
          direction: 'forward',
          speed: 200,
        ),
        controlMode: 'MANUAL',
      );

      await expectLater(
        client.move(
          RobotMoveRequest(
            requestId: 'c1234567-89ab-4cde-8f01-23456789abcd',
            direction: 'left',
            speed: 200,
          ),
          controlMode: 'MANUAL',
        ),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.code,
            'code',
            'command_in_progress',
          ),
        ),
      );
      expect(transport.postCount, 1);

      responseCompleter.complete(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-1","command":"forward",'
              '"status":"dispatched","control_mode":"MANUAL",'
              '"error_code":null,"timestamp":"2026-11-05T12:00:00Z"}',
        ),
      );
      await first;
    });

    test('coalesces STOP taps while a request is in flight', () async {
      final responseCompleter = Completer<PiApiHttpResponse>();
      transport.postCompleter = responseCompleter;
      const requestId = 'c1234567-89ab-4cde-8f01-23456789abcd';

      final first = client.stop(requestId: requestId);
      final repeated = client.stop(requestId: requestId);

      expect(transport.postCount, 1);
      await expectLater(
        client.move(
          RobotMoveRequest(
            requestId: 'd1234567-89ab-4cde-8f01-23456789abcd',
            direction: 'forward',
            speed: 200,
          ),
          controlMode: 'MANUAL',
        ),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.code,
            'code',
            'command_in_progress',
          ),
        ),
      );

      responseCompleter.complete(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"c1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-stop","command":"stop",'
              '"status":"dispatched","control_mode":"AUTO",'
              '"error_code":null,"timestamp":"2026-11-05T12:00:00Z"}',
        ),
      );

      expect((await first).commandId, (await repeated).commandId);
      expect(transport.postCount, 1);
    });

    test('looks up a command on the confirmed route', () async {
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 200,
          body:
              '{"request_id":"request-1","command_id":"cmd-1",'
              '"command":"forward","status":"acknowledged",'
              '"error_code":null,"timestamp":"2026-11-05T12:00:00Z",'
              '"control_mode":"MANUAL"}',
        ),
      );

      final result = await client.getCommand('cmd-1');

      expect(transport.lastUri!.path, '/api/v1/robot/commands/cmd-1');
      expect(transport.lastHeaders!['Authorization'], 'Bearer test-token');
      expect(result.requestId, 'request-1');
      expect(result.status, 'acknowledged');
    });

    test(
      'translates FastAPI validation errors without losing details',
      () async {
        transport.responses.add(
          const PiApiHttpResponse(
            statusCode: 422,
            body: '{"detail":[{"msg":"invalid speed"}]}',
          ),
        );

        await expectLater(
          client.setMode(RobotMode.automatic),
          throwsA(
            isA<PiApiException>()
                .having((error) => error.code, 'code', 'invalid_input')
                .having((error) => error.statusCode, 'statusCode', 422)
                .having(
                  (error) => error.details,
                  'details',
                  isA<List<dynamic>>(),
                ),
          ),
        );
      },
    );

    test('maps an oversized command body to a specific client error', () async {
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 413,
          body: '{"detail":{"error":"request_body_too_large"}}',
        ),
      );

      await expectLater(
        client.setMode(RobotMode.manual),
        throwsA(
          isA<PiApiException>()
              .having((error) => error.code, 'code', 'payload_too_large')
              .having((error) => error.statusCode, 'statusCode', 413)
              .having((error) => error.details, 'details', {
                'error': 'request_body_too_large',
              }),
        ),
      );
    });

    test('maps an unsupported request content type explicitly', () async {
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 415,
          body:
              '{"detail":{"error":"unsupported_media_type",'
              '"error_code":"UNSUPPORTED_MEDIA_TYPE",'
              '"supported":["application/json"]}}',
        ),
      );

      await expectLater(
        client.setMode(RobotMode.manual),
        throwsA(
          isA<PiApiException>()
              .having((error) => error.code, 'code', 'unsupported_media_type')
              .having(
                (error) => error.backendCode,
                'backendCode',
                'UNSUPPORTED_MEDIA_TYPE',
              )
              .having((error) => error.statusCode, 'statusCode', 415),
        ),
      );
    });

    test('maps RATE_LIMITED details and keeps normal STOP available', () async {
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 429,
          body:
              '{"detail":{"error":"rate_limited",'
              '"error_code":"RATE_LIMITED",'
              '"retry_after_seconds":0.2}}',
          headers: {'Retry-After': '1'},
        ),
      );
      transport.responses.add(
        const PiApiHttpResponse(
          statusCode: 202,
          body:
              '{"request_id":"c1234567-89ab-4cde-8f01-23456789abcd",'
              '"command_id":"cmd-stop","command":"stop",'
              '"status":"dispatched","control_mode":"AUTO",'
              '"error_code":null,"timestamp":"2026-11-07T12:00:00Z"}',
        ),
      );

      late PiApiException rateLimit;
      try {
        await client.setMode(RobotMode.manual);
        fail('Expected the Pi rate limit response.');
      } on PiApiException catch (error) {
        rateLimit = error;
      }

      expect(rateLimit.code, 'rate_limited');
      expect(rateLimit.backendCode, 'RATE_LIMITED');
      expect(rateLimit.statusCode, 429);
      expect(rateLimit.retryAfter, const Duration(milliseconds: 200));
      expect(rateLimit.retryable, isTrue);
      expect(rateLimit.message, contains('No command was sent'));
      expect(rateLimit.details, {
        'error': 'rate_limited',
        'error_code': 'RATE_LIMITED',
        'retry_after_seconds': 0.2,
      });

      final stop = await client.stop(
        requestId: 'c1234567-89ab-4cde-8f01-23456789abcd',
      );
      expect(stop.command, 'stop');
      expect(transport.lastUri!.path, '/api/v1/robot/stop');
      expect(transport.postCount, 2);
    });

    test(
      'uses Retry-After header when the rate-limit body omits its delay',
      () async {
        transport.responses.add(
          const PiApiHttpResponse(
            statusCode: 429,
            body:
                '{"detail":{"error":"rate_limited",'
                '"error_code":"RATE_LIMITED"}}',
            headers: {'retry-after': '0.5'},
          ),
        );

        await expectLater(
          client.setMode(RobotMode.manual),
          throwsA(
            isA<PiApiException>()
                .having((error) => error.code, 'code', 'rate_limited')
                .having(
                  (error) => error.retryAfter,
                  'retryAfter',
                  const Duration(milliseconds: 500),
                ),
          ),
        );
      },
    );

    test(
      'maps API_BUSY as retryable and confirms it was not dispatched',
      () async {
        transport.responses.add(
          const PiApiHttpResponse(
            statusCode: 503,
            body:
                '{"detail":{"error":"command_queue_busy",'
                '"error_code":"API_BUSY","retryable":true}}',
          ),
        );

        await expectLater(
          client.setMode(RobotMode.manual),
          throwsA(
            isA<PiApiException>()
                .having((error) => error.code, 'code', 'api_busy')
                .having((error) => error.backendCode, 'backendCode', 'API_BUSY')
                .having((error) => error.retryable, 'retryable', isTrue)
                .having(
                  (error) => error.message,
                  'message',
                  contains('request was not sent'),
                ),
          ),
        );
      },
    );
    test('reports malformed JSON responses explicitly', () async {
      transport.responses.add(
        const PiApiHttpResponse(statusCode: 200, body: 'not-json'),
      );

      await expectLater(
        client.getStatus(),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.code,
            'code',
            'malformed_response',
          ),
        ),
      );
    });

    test('translates a disconnected Pi into an unreachable error', () async {
      transport.failure = const SocketException('No route to host');

      await expectLater(
        client.getStatus(),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.code,
            'code',
            'unreachable',
          ),
        ),
      );
    });

    test('does not send protected calls without a token', () async {
      final unauthenticatedClient = PiApiClient(
        baseUri: Uri.parse('http://pi.test:8000'),
        transport: transport,
      );

      await expectLater(
        unauthenticatedClient.stop(
          requestId: 'c1234567-89ab-4cde-8f01-23456789abcd',
        ),
        throwsA(
          isA<PiApiException>().having(
            (error) => error.code,
            'code',
            'credentials_not_configured',
          ),
        ),
      );
      expect(transport.lastUri, isNull);
    });
  });
}

class _FakeTransport implements PiApiTransport {
  final List<PiApiHttpResponse> responses = [];
  Object? failure;
  Completer<PiApiHttpResponse>? postCompleter;
  int postCount = 0;
  Uri? lastUri;
  Map<String, String>? lastHeaders;
  Object? lastJsonBody;

  @override
  Future<PiApiHttpResponse> get(
    Uri uri, {
    required Map<String, String> headers,
  }) async {
    lastUri = uri;
    lastHeaders = headers;
    final error = failure;
    if (error != null) throw error;
    return responses.removeAt(0);
  }

  @override
  Future<PiApiHttpResponse> post(
    Uri uri, {
    required Map<String, String> headers,
    Object? jsonBody,
  }) async {
    postCount++;
    lastUri = uri;
    lastHeaders = headers;
    lastJsonBody = jsonBody;
    final error = failure;
    if (error != null) throw error;
    final completer = postCompleter;
    if (completer != null) return completer.future;
    return responses.removeAt(0);
  }

  @override
  void close() {}
}
