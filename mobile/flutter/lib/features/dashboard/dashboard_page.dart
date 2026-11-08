import 'package:flutter/material.dart';

import '../../core/pi_api_exception.dart';
import '../../models/pi_status.dart';
import '../../services/pi_api_client.dart';
import '../../widgets/zeno_offline_notice.dart';

/// Dashboard for the fields currently exposed by GET /api/v1/status.
/// A missing client means no Pi address has been configured in the app yet.
class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, this.apiClient});

  final PiApiClient? apiClient;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  PiStatus? _status;
  String? _error;
  bool _loading = false;
  bool _stale = false;

  @override
  void initState() {
    super.initState();
    if (widget.apiClient != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
    }
  }

  Future<void> _refresh() async {
    final client = widget.apiClient;
    if (client == null || _loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final status = await client.getStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _stale = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is PiApiException ? error.message : error.toString();
        // Keep previously received values only when visibly marked stale.
        _stale = _status != null;
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final clientConfigured = widget.apiClient != null;
    final connected = _status != null && !_stale;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Robot overview',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            IconButton(
              tooltip: 'Refresh robot status',
              constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
              onPressed: clientConfigured && !_loading ? _refresh : null,
              icon: _loading
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 12),
        _ConnectionCard(
          label: !clientConfigured
              ? 'Not configured'
              : connected
              ? 'Connected to Pi API'
              : 'Unavailable',
          connected: connected,
          configured: clientConfigured,
        ),
        if (!clientConfigured) ...[
          const SizedBox(height: 12),
          const ZenoOfflineNotice(state: ZenoNoticeState.unavailable),
          const SizedBox(height: 8),
          const Text(
            'The Pi address is not configured yet. Robot status will appear '
            'here after a connection is set up.',
            textAlign: TextAlign.center,
          ),
        ] else if (_loading && _status == null) ...[
          const SizedBox(height: 16),
          const ZenoOfflineNotice(state: ZenoNoticeState.loading),
        ] else if (_error != null && _status == null) ...[
          const SizedBox(height: 16),
          const ZenoOfflineNotice(state: ZenoNoticeState.error),
          const SizedBox(height: 8),
          Text(_error!, textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Center(
            child: TextButton.icon(
              onPressed: _loading ? null : _refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ),
        ] else if (_status != null) ...[
          if (_stale) ...[
            const SizedBox(height: 12),
            const ZenoOfflineNotice(state: ZenoNoticeState.error),
            const SizedBox(height: 8),
            const Text(
              'Last received status is stale. Refresh to try again.',
              textAlign: TextAlign.center,
            ),
          ],
          const SizedBox(height: 16),
          Text(
            'Reported by Pi',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          _StatusCard(
            stale: _stale,
            values: {
              'API status': _status!.api,
              'ESP32 transport': _status!.esp32Transport,
              'Controller readiness': _status!.controllerReadiness,
              'Control mode': _status!.controlMode,
            },
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center),
          ],
        ],
      ],
    );
  }
}

class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({
    required this.label,
    required this.connected,
    required this.configured,
  });

  final String label;
  final bool connected;
  final bool configured;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final color = connected
        ? colors.primary
        : configured
        ? colors.error
        : colors.onSurfaceVariant;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(
              connected ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
              color: color,
            ),
            const SizedBox(width: 12),
            const Expanded(child: Text('Pi API connection')),
            Text(label, style: TextStyle(color: color)),
          ],
        ),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.values, required this.stale});

  final Map<String, String> values;
  final bool stale;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Column(
          children: [
            for (final entry in values.entries)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(entry.key),
                trailing: Text(
                  stale ? '${entry.value} · stale' : entry.value,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
