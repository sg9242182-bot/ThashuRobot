import 'package:flutter/material.dart';

import '../../services/wifi_provisioning_client.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, this.onOpenManualControl});

  final VoidCallback? onOpenManualControl;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _ssid = TextEditingController();
  final _password = TextEditingController();
  final _wifiClient = WifiProvisioningClient();
  bool _busy = false;
  String? _status;
  bool _failed = false;

  @override
  void dispose() {
    _ssid.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _sendHotspotCredentials() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _failed = false;
      _status = 'Searching for Thashu over Bluetooth…';
    });
    try {
      final result = await _wifiClient.provision(
        ssid: _ssid.text,
        password: _password.text,
      );
      if (!mounted) return;
      setState(() => _status = result);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        _status = error.toString().replaceFirst('Bad state: ', '');
      });
    } finally {
      // The phone does not retain the hotspot key after this attempt.
      _password.clear();
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Text('Settings', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Connect Thashu to a phone hotspot',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                const Text(
                  'This works without internet. Turn on your phone hotspot, then '
                  'hold the Pi button for 3 seconds. The setup window stays open '
                  'for 60 seconds.',
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _ssid,
                  enabled: !_busy,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(
                    labelText: 'Hotspot name (SSID)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _password,
                  enabled: !_busy,
                  obscureText: true,
                  autocorrect: false,
                  enableSuggestions: false,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _busy ? null : _sendHotspotCredentials(),
                  decoration: const InputDecoration(
                    labelText: 'Hotspot password',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _sendHotspotCredentials,
                    icon: _busy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.bluetooth_searching),
                    label: Text(_busy ? 'Connecting…' : 'Connect & send'),
                  ),
                ),
                if (_status != null) ...[
                  const SizedBox(height: 10),
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      _status!,
                      style: TextStyle(
                        color: _failed
                            ? Theme.of(context).colorScheme.error
                            : Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                Text(
                  'The password is sent to the Pi over an encrypted Bluetooth '
                  'connection and is not saved in the app. The Pi stores it '
                  'locally so it can reconnect after reboot.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        Text('Competition Mode', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.flag_outlined),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Competition quick start',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                FilledButton.tonalIcon(
                  onPressed: widget.onOpenManualControl,
                  icon: const Icon(Icons.gamepad_outlined),
                  label: const Text('Open Manual Control'),
                ),
                const SizedBox(height: 12),
                const Text(
                  '1. Check connection and reported mode on Dashboard.',
                ),
                const SizedBox(height: 6),
                const Text(
                  '2. Use the existing Manual Control screen for movement.',
                ),
                const SizedBox(height: 6),
                const Text(
                  '3. Use normal STOP to request a stop. Emergency Stop is '
                  'unavailable, and a command acknowledgement does not confirm '
                  'the robot physically stopped.',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
