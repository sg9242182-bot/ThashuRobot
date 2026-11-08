import 'package:flutter/material.dart';

import '../../core/pi_api_exception.dart';
import '../../models/robot_command.dart';
import '../../models/robot_mode.dart';
import '../../models/pi_status.dart';
import '../../models/robot_move_request.dart';
import '../../services/pi_api_client.dart';
import '../../widgets/zeno_offline_notice.dart';

/// Manual controls use only the Pi's confirmed REST API.
/// A dispatched response is not treated as proof of physical movement/stop.
class ManualControlPage extends StatefulWidget {
  const ManualControlPage({super.key, this.apiClient});

  final PiApiClient? apiClient;

  @override
  State<ManualControlPage> createState() => _ManualControlPageState();
}

class _ManualControlPageState extends State<ManualControlPage>
    with WidgetsBindingObserver {
  PiStatus? _status;
  bool _loadingStatus = false;
  bool _statusStale = false;
  bool _modeBusy = false;
  bool _moveBusy = false;
  bool _stopBusy = false;
  bool _appPaused = false;
  double _speed = 200;
  String? _message;
  String? _commandId;
  String? _commandStatus;

  bool get _manualReady =>
      widget.apiClient != null &&
      !_appPaused &&
      !_loadingStatus &&
      !_statusStale &&
      _status?.api == 'ok' &&
      _status?.esp32Transport == 'connected' &&
      _status?.controlMode == 'MANUAL' &&
      !_modeBusy &&
      !_moveBusy &&
      !_stopBusy &&
      !_commandNeedsAttention;

  bool get _commandNeedsAttention =>
      _commandStatus == 'unknown' ||
      (_commandId != null &&
          !const {
            'acknowledged',
            'safety_error',
            'timed_out',
          }.contains(_commandStatus));

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.apiClient != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _refreshStatus());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant ManualControlPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.apiClient != widget.apiClient) {
      _status = null;
      _statusStale = false;
      _message = null;
      if (widget.apiClient != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _refreshStatus();
        });
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_appPaused) {
        setState(() => _appPaused = false);
        _refreshStatus();
      }
      return;
    }

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      if (!_appPaused) {
        setState(() {
          _appPaused = true;
          _statusStale = true;
          _message =
              'App inactive. The robot may still be moving; '
              'connection loss does not confirm it stopped.';
        });
      }
    }
  }

  Future<void> _refreshStatus({bool clearMessage = true}) async {
    final client = widget.apiClient;
    if (client == null || _loadingStatus) return;

    setState(() {
      _loadingStatus = true;
      if (clearMessage) _message = null;
    });
    try {
      final status = await client.getStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _statusStale = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _statusStale = true;
        _message = _errorMessage(error);
      });
    } finally {
      if (mounted) setState(() => _loadingStatus = false);
    }
  }

  Future<void> _setMode(String mode) async {
    final client = widget.apiClient;
    if (client == null ||
        _modeBusy ||
        _moveBusy ||
        _stopBusy ||
        _commandNeedsAttention) {
      return;
    }
    setState(() {
      _modeBusy = true;
      _message = null;
    });
    try {
      final response = await client.setMode(
        mode == 'MANUAL' ? RobotMode.manual : RobotMode.automatic,
      );
      if (!mounted) return;
      setState(() {
        _message = 'Pi reported mode ${response.mode}: ${response.status}.';
      });
      await _refreshStatus();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        if (_isConnectionUncertain(error)) _statusStale = true;
        _message = _errorMessage(error);
      });
    } finally {
      if (mounted) setState(() => _modeBusy = false);
    }
  }

  Future<void> _move(String direction) async {
    final client = widget.apiClient;
    final mode = _status?.controlMode;
    if (client == null || !_manualReady || mode == null) return;
    setState(() {
      _moveBusy = true;
      _message = null;
    });
    try {
      final result = await client.move(
        RobotMoveRequest(
          requestId: RobotRequestId.generate(),
          direction: direction,
          speed: _speed.round(),
        ),
        controlMode: mode,
      );
      if (!mounted) return;
      setState(() {
        _commandId = result.commandId;
        _commandStatus = result.status;
        _message = _commandMessage(result);
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        if (_isConnectionUncertain(error)) {
          _statusStale = true;
          _commandStatus = 'unknown';
        }
        _message = _errorMessage(error);
      });
    } finally {
      if (mounted) setState(() => _moveBusy = false);
    }
  }

  Future<void> _stop() async {
    final client = widget.apiClient;
    if (client == null || _stopBusy) return;
    setState(() {
      _stopBusy = true;
      _message = null;
    });
    try {
      final result = await client.stop(requestId: RobotRequestId.generate());
      if (!mounted) return;
      final stopModeMessage = result.controlMode == 'AUTO'
          ? 'Pi reported AUTO paused.'
          : 'Pi reported mode ${result.controlMode}.';
      setState(() {
        _commandId = result.commandId;
        _commandStatus = result.status;
        _message = result.command == 'stop' && result.status == 'dispatched'
            ? '$stopModeMessage STOP was dispatched; ESP32 acknowledgement '
                  'is pending, and physical stopping is not confirmed.'
            : _commandMessage(result);
      });
      await _refreshStatus(clearMessage: false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        if (_isConnectionUncertain(error)) {
          _statusStale = true;
          _commandStatus = 'unknown';
        }
        _message = _errorMessage(error);
      });
    } finally {
      if (mounted) setState(() => _stopBusy = false);
    }
  }

  Future<void> _checkCommandResult() async {
    final client = widget.apiClient;
    final commandId = _commandId;
    if (client == null || commandId == null || _moveBusy || _stopBusy) return;
    setState(() => _message = null);
    try {
      final result = await client.getCommand(commandId);
      if (!mounted) return;
      setState(() {
        _commandStatus = result.status;
        _message = _commandMessage(result);
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        if (_isConnectionUncertain(error)) {
          _statusStale = true;
          _commandStatus = 'unknown';
        }
        _message = _errorMessage(error);
      });
    }
  }

  String _commandMessage(RobotCommandResult result) => switch (result.status) {
    'dispatched' || 'dispatching' =>
      '${result.command} was sent by the Pi. ESP32 acknowledgement is pending; '
          'movement is not confirmed.',
    'acknowledged' =>
      'ESP32 acknowledged ${result.command}. Physical movement or stopping '
          'is not confirmed.',
    'safety_error' =>
      'The robot rejected ${result.command} for safety: '
          '${result.errorCode ?? 'reason not provided'}.',
    'timed_out' => '${result.command} acknowledgement timed out.',
    'unknown' =>
      'The result of ${result.command} is unknown. Do not assume the robot '
          'stopped.',
    _ => 'Pi reported command status: ${result.status}.',
  };

  String _errorMessage(Object error) {
    if (error is PiApiException) {
      if (const {
        'timeout',
        'unreachable',
        'connection_error',
        'malformed_response',
        'server_error',
      }.contains(error.code)) {
        return 'Connection lost; command outcome may be unknown. Do not '
            'assume the robot stopped. ${error.message}';
      }
      if (error.statusCode == 409 || error.statusCode == 422) {
        return 'Command rejected: ${error.message}';
      }
      return error.message;
    }
    return error.toString();
  }

  bool _isConnectionUncertain(Object error) =>
      error is! PiApiException ||
      const {
        'timeout',
        'unreachable',
        'connection_error',
        'malformed_response',
        'server_error',
        'service_unavailable',
      }.contains(error.code);

  @override
  Widget build(BuildContext context) {
    final clientConfigured = widget.apiClient != null;
    final mode = _status?.controlMode ?? 'unknown';
    final statusLabel = !clientConfigured
        ? 'Not configured'
        : _appPaused
        ? 'App inactive · last status stale'
        : _statusStale
        ? 'Unavailable · last status stale'
        : _status == null
        ? 'Connecting'
        : 'Pi reachable';
    final colors = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Manual Control',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            IconButton(
              tooltip: 'Refresh robot status',
              onPressed: clientConfigured && !_loadingStatus
                  ? _refreshStatus
                  : null,
              icon: _loadingStatus
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.refresh),
            ),
          ],
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Column(
              children: [
                Row(
                  children: [
                    Icon(
                      _status == null || _statusStale
                          ? Icons.cloud_off_outlined
                          : Icons.cloud_done_outlined,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Pi API connection'),
                          Text(statusLabel),
                        ],
                      ),
                    ),
                  ],
                ),
                const Divider(height: 20),
                if (clientConfigured || _statusStale)
                  _statusRow(
                    'Reported mode',
                    _statusStale ? '$mode · stale' : mode,
                  ),
                if (_status != null) ...[
                  _statusRow(
                    'Controller readiness',
                    _status!.controllerReadiness,
                  ),
                  _statusRow('ESP32 transport', _status!.esp32Transport),
                ],
              ],
            ),
          ),
        ),
        if (!clientConfigured) ...[
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: colors.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Row(
              children: [
                Icon(Icons.block_outlined),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'The Pi address and token are not configured. Controls '
                        'remain disabled until the Pi API is connected.',
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ] else if (_status == null && !_statusStale) ...[
          const SizedBox(height: 8),
          ZenoOfflineNotice(
            state: _loadingStatus
                ? ZenoNoticeState.loading
                : ZenoNoticeState.error,
          ),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!, textAlign: TextAlign.center),
          ],
        ] else if (_statusStale) ...[
          const SizedBox(height: 8),
          const ZenoOfflineNotice(state: ZenoNoticeState.error),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!, textAlign: TextAlign.center),
          ],
        ],
        const SizedBox(height: 8),
        Text('Select mode', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                key: const ValueKey('mode-auto-button'),
                onPressed:
                    clientConfigured &&
                        !_modeBusy &&
                        !_moveBusy &&
                        !_stopBusy &&
                        !_commandNeedsAttention &&
                        !_statusStale &&
                        _status != null
                    ? () => _setMode('AUTO')
                    : null,
                child: const Text('AUTO'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton.tonal(
                key: const ValueKey('mode-manual-button'),
                onPressed:
                    clientConfigured &&
                        !_modeBusy &&
                        !_moveBusy &&
                        !_stopBusy &&
                        !_commandNeedsAttention &&
                        !_statusStale &&
                        _status != null
                    ? () => _setMode('MANUAL')
                    : null,
                child: _modeBusy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('MANUAL'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text('Speed', style: Theme.of(context).textTheme.titleMedium),
        Row(
          children: [
            Expanded(
              child: Slider(
                key: const ValueKey('manual-speed-slider'),
                min: 0,
                max: 255,
                divisions: 255,
                value: _speed,
                label: _speed.round().toString(),
                onChanged: _manualReady && !_moveBusy
                    ? (value) => setState(() => _speed = value)
                    : null,
              ),
            ),
            SizedBox(width: 42, child: Text(_speed.round().toString())),
          ],
        ),
        const SizedBox(height: 4),
        Center(
          child: Column(
            children: [
              _directionButton(
                direction: 'forward',
                label: 'Move forward',
                icon: Icons.keyboard_arrow_up,
                enabled: _manualReady,
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _directionButton(
                    direction: 'left',
                    label: 'Turn left',
                    icon: Icons.keyboard_arrow_left,
                    enabled: _manualReady,
                  ),
                  const SizedBox(width: 8),
                  _directionButton(
                    direction: 'right',
                    label: 'Turn right',
                    icon: Icons.keyboard_arrow_right,
                    enabled: _manualReady,
                  ),
                ],
              ),
              _directionButton(
                direction: 'backward',
                label: 'Move backward',
                icon: Icons.keyboard_arrow_down,
                enabled: _manualReady,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 56,
          child: FilledButton.icon(
            key: const ValueKey('manual-stop-button'),
            onPressed: clientConfigured && !_stopBusy ? _stop : null,
            style: FilledButton.styleFrom(
              backgroundColor: colors.error,
              foregroundColor: colors.onError,
            ),
            icon: _stopBusy
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.stop_circle_outlined),
            label: const Text('STOP'),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'A direction tap sends a move command. Press STOP to request '
          'cancellation. Losing the app connection does not confirm the '
          'robot stopped.',
          textAlign: TextAlign.center,
        ),
        if (_moveBusy) ...[
          const SizedBox(height: 8),
          const LinearProgressIndicator(),
          const SizedBox(height: 4),
          const Text('Move request in progress', textAlign: TextAlign.center),
        ],
        if (_message != null && !_statusStale) ...[
          const SizedBox(height: 12),
          Semantics(liveRegion: true, child: Text(_message!)),
        ],
        if (_commandId != null) ...[
          const SizedBox(height: 4),
          Text('Command status: ${_commandStatus ?? 'unknown'}'),
          TextButton.icon(
            onPressed: _moveBusy || _stopBusy ? null : _checkCommandResult,
            icon: const Icon(Icons.sync),
            label: const Text('Check command result'),
          ),
        ],
        const SizedBox(height: 8),
        const Text(
          'Emergency Stop is unavailable: the current API has no approved '
          'latched Emergency Stop command. Use STOP to request a normal stop.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12),
        ),
      ],
    );
  }

  Widget _directionButton({
    required String direction,
    required String label,
    required IconData icon,
    required bool enabled,
  }) {
    final words = label.split(' ');

    return SizedBox(
      width: 100,
      height: 64,
      child: FilledButton.tonal(
        key: ValueKey('move-$direction-button'),
        onPressed: enabled ? () => _move(direction) : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 20),
            const SizedBox(height: 2),
            Text(
              '${words.first}\n${words.skip(1).join(' ')}',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        Flexible(child: Text(value, textAlign: TextAlign.end)),
      ],
    ),
  );
}
