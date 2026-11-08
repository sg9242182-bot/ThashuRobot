import 'dart:async';

import 'package:flutter/material.dart';

import '../../models/telemetry_event.dart';
import '../../services/pi_telemetry_client.dart';

class TelemetryDiagnosticsPage extends StatefulWidget {
  const TelemetryDiagnosticsPage({super.key, this.client});

  final PiTelemetryClient? client;

  @override
  State<TelemetryDiagnosticsPage> createState() =>
      _TelemetryDiagnosticsPageState();
}

class _TelemetryDiagnosticsPageState extends State<TelemetryDiagnosticsPage> {
  StreamSubscription<TelemetryConnectionState>? _stateSubscription;
  StreamSubscription<TelemetryEvent>? _eventSubscription;
  Timer? _sensorStaleTimer;
  TelemetryConnectionState _state = TelemetryConnectionState.disconnected;
  TelemetryEvent? _latestEvent;
  SensorTelemetryFrame? _sensorFrame;
  DateTime? _sensorPiReceivedAt;
  bool _sensorFresh = false;
  bool _hasCurrentConnectionEvent = false;

  @override
  void initState() {
    super.initState();
    _attachClient();
  }

  @override
  void didUpdateWidget(covariant TelemetryDiagnosticsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.client != widget.client) {
      _cancelSubscriptions();
      _attachClient();
    }
  }

  void _attachClient() {
    final client = widget.client;
    _state = client?.state ?? TelemetryConnectionState.disconnected;
    _latestEvent = client?.latestEvent;
    _sensorFrame = client?.latestSensorFrame;
    _sensorPiReceivedAt = client?.latestSensorPiReceivedAt;
    _hasCurrentConnectionEvent = client?.hasCurrentConnectionEvent ?? false;
    if (client == null) return;
    _updateSensorFreshness(client.latestSensorFrameReceivedAt);

    _stateSubscription = client.states.listen((state) {
      if (mounted) {
        setState(() {
          _state = state;
          _hasCurrentConnectionEvent = client.hasCurrentConnectionEvent;
        });
      }
    });
    _eventSubscription = client.events.listen((event) {
      if (mounted) {
        setState(() {
          _latestEvent = event;
          _hasCurrentConnectionEvent = client.hasCurrentConnectionEvent;
          if (event is Esp32LineEvent && event.sensorFrame != null) {
            _sensorFrame = event.sensorFrame;
            _sensorPiReceivedAt = event.receivedAt;
            _updateSensorFreshness(client.latestSensorFrameReceivedAt);
          }
        });
      }
    });
    unawaited(client.connect());
  }

  void _cancelSubscriptions() {
    unawaited(_stateSubscription?.cancel());
    unawaited(_eventSubscription?.cancel());
    _stateSubscription = null;
    _eventSubscription = null;
    _sensorStaleTimer?.cancel();
    _sensorStaleTimer = null;
  }

  void _updateSensorFreshness(DateTime? receivedLocallyAt) {
    _sensorStaleTimer?.cancel();
    if (receivedLocallyAt == null) {
      _sensorFresh = false;
      return;
    }

    final remaining =
        const Duration(seconds: 1) -
        DateTime.now().difference(receivedLocallyAt);
    if (remaining <= Duration.zero) {
      _sensorFresh = false;
      return;
    }

    _sensorFresh = true;
    _sensorStaleTimer = Timer(remaining, () {
      if (mounted) setState(() => _sensorFresh = false);
    });
  }

  @override
  void dispose() {
    _cancelSubscriptions();
    super.dispose();
  }

  Future<void> _connect() async {
    final client = widget.client;
    if (client == null) return;
    await client.connect();
    if (mounted) setState(() => _state = client.state);
  }

  String get _stateLabel => switch (_state) {
    TelemetryConnectionState.disconnected => 'Disconnected',
    TelemetryConnectionState.connecting => 'Connecting',
    TelemetryConnectionState.connected => 'Connected',
    TelemetryConnectionState.reconnecting => 'Reconnecting',
    TelemetryConnectionState.failed => 'Connection failed',
  };

  IconData get _stateIcon => switch (_state) {
    TelemetryConnectionState.disconnected => Icons.cloud_off_outlined,
    TelemetryConnectionState.connecting ||
    TelemetryConnectionState.reconnecting => Icons.sync,
    TelemetryConnectionState.connected => Icons.cloud_done_outlined,
    TelemetryConnectionState.failed => Icons.error_outline,
  };

  @override
  Widget build(BuildContext context) {
    final client = widget.client;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Telemetry',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            FilledButton.tonalIcon(
              onPressed:
                  client == null ||
                      _state == TelemetryConnectionState.connecting ||
                      _state == TelemetryConnectionState.reconnecting ||
                      _state == TelemetryConnectionState.connected
                  ? null
                  : _connect,
              icon: const Icon(Icons.sync),
              label: const Text('Connect / retry'),
            ),
          ],
        ),
        Card(
          child: ListTile(
            leading: Icon(_stateIcon),
            title: const Text('Telemetry socket'),
            subtitle: Text(client == null ? 'Not configured' : _stateLabel),
          ),
        ),
        if (client == null) ...[
          const Text('Pi telemetry is not configured.'),
          const SizedBox(height: 4),
          const Text(
            'A Pi address and token are required before live data can appear.',
          ),
          const SizedBox(height: 8),
          const Text(
            'Placeholder: Diagnostics will appear when data is available.',
          ),
          const SizedBox(height: 16),
          const Card(
            child: ListTile(
              leading: Icon(Icons.help_outline),
              title: Text('Robot self-checks unavailable'),
              subtitle: Text(
                'The current API does not provide PASS, WARNING, FAIL, or '
                'UNKNOWN diagnostic results.',
              ),
            ),
          ),
        ] else ...[
          if (_state == TelemetryConnectionState.failed)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Telemetry connection failed. Check the Pi address, network, '
                  'and token, then retry.',
                ),
              ),
            ),
          const SizedBox(height: 8),
          _sensorTelemetryCard(),
          const SizedBox(height: 8),
          Text(
            'Latest received message',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          _latestEvent == null
              ? const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Waiting for telemetry events.'),
                  ),
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (!_hasCurrentConnectionEvent)
                      const Card(
                        child: Padding(
                          padding: EdgeInsets.all(12),
                          child: Text(
                            'Last message is stale: this connection has not '
                            'received a new event.',
                          ),
                        ),
                      ),
                    _eventCard(_latestEvent!),
                  ],
                ),
          const SizedBox(height: 8),
          const Text(
            'Reconnect is manual. A connected socket does not prove the robot '
            'is healthy. Sensor readings become stale after one second without '
            'a new sensor TEL frame. Raw ESP32 lines do not change Pi-reported '
            'status.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12),
          ),
        ],
      ],
    );
  }

  Widget _sensorTelemetryCard() {
    final frame = _sensorFrame;
    final freshness = frame == null
        ? 'Waiting for sensor frame'
        : _sensorFresh
        ? 'Fresh'
        : 'Stale';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(child: Text('Sensor telemetry')),
                Text(freshness),
              ],
            ),
            if (frame == null) ...[
              const SizedBox(height: 8),
              const Text('No well-formed sensor TEL frame received yet.'),
            ] else ...[
              const SizedBox(height: 8),
              _detailRow('ToF left', frame.tofLeft.displayValue),
              _detailRow('ToF center', frame.tofCenter.displayValue),
              _detailRow('ToF right', frame.tofRight.displayValue),
              _detailRow('Rear ultrasonic', frame.ultrasonicRear.displayValue),
              _detailRow(
                'Pi received at',
                _sensorPiReceivedAt!.toUtc().toIso8601String(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _eventCard(TelemetryEvent event) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: switch (event) {
        CommandResultEvent result => _commandResultContent(result),
        Esp32LineEvent lineEvent => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Raw ESP32 line'),
            const SizedBox(height: 8),
            SelectableText(lineEvent.line),
            if (lineEvent.sensorParseError != null) ...[
              const SizedBox(height: 8),
              Text('Sensor frame ignored: ${lineEvent.sensorParseError}'),
            ],
          ],
        ),
        UnknownTelemetryEvent unknown => Text(
          'Unknown telemetry event type: ${unknown.type}. Ignored.',
        ),
        MalformedTelemetryEvent malformed => Text(
          'Malformed telemetry message ignored: ${malformed.reason}',
        ),
      },
    ),
  );

  Widget _commandResultContent(CommandResultEvent event) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text('Command result'),
      const SizedBox(height: 8),
      _detailRow('Command ID', event.commandId),
      if (event.requestId != null) _detailRow('Request ID', event.requestId!),
      _detailRow('Status', event.status),
      if (event.errorCode != null) _detailRow('Error', event.errorCode!),
      _detailRow('Event time', event.timestamp),
    ],
  );

  Widget _detailRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 110, child: Text(label)),
        Expanded(child: SelectableText(value)),
      ],
    ),
  );
}
