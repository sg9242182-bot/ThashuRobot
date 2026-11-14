import 'package:flutter/material.dart';

import '../../services/wifi_provisioning_client.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({
    super.key,
    this.initialAddress,
    this.initialCertificateFingerprint,
    this.tokenConfigured = false,
    this.isLoading = false,
    this.onSaveConnection,
    this.onSaveConnectionWithPin,
    this.onClearConnection,
    this.onOpenManualControl,
    this.wifiProvisioningClient,
  });

  final String? initialAddress;
  final String? initialCertificateFingerprint;
  final bool tokenConfigured;
  final bool isLoading;
  final Future<String?> Function(String address, String token)? onSaveConnection;
  final Future<String?> Function(String address, String token, String fingerprint)? onSaveConnectionWithPin;
  final Future<void> Function()? onClearConnection;
  final VoidCallback? onOpenManualControl;
  final WifiProvisioningService? wifiProvisioningClient;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _addressController;
  final TextEditingController _tokenController = TextEditingController();
  late final TextEditingController _fingerprintController;
  bool _saving = false;
  String? _message;
  final TextEditingController _hotspotSsidController = TextEditingController();
  final TextEditingController _hotspotPasswordController = TextEditingController();
  late final WifiProvisioningService _wifiProvisioningClient;
  bool _provisioning = false;
  bool _provisioningFailed = false;
  String? _provisioningMessage;

  @override
  void initState() {
    super.initState();
    _wifiProvisioningClient =
        widget.wifiProvisioningClient ?? WifiProvisioningClient();
    _addressController = TextEditingController(text: widget.initialAddress ?? '');
    _fingerprintController = TextEditingController(text: widget.initialCertificateFingerprint ?? '');
  }

  @override
  void didUpdateWidget(covariant SettingsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialAddress != widget.initialAddress) {
      _addressController.text = widget.initialAddress ?? '';
    }
    if (oldWidget.initialCertificateFingerprint != widget.initialCertificateFingerprint) {
      _fingerprintController.text = widget.initialCertificateFingerprint ?? '';
    }
  }

  @override
  void dispose() {
    _addressController.dispose();
    _tokenController.dispose();
    _fingerprintController.dispose();
    _hotspotSsidController.dispose();
    _hotspotPasswordController.dispose();
    super.dispose();
  }

  String _provisioningStatusMessage(String status) => switch (status) {
    'found' => 'Thashu found. Connecting over Bluetooth…',
    'waiting' => 'The Pi setup window is ready. Sending Wi-Fi credentials…',
    'credentials_sent' => 'Credentials sent. Waiting for the Pi to report receipt…',
    'received' => 'The Pi reports that it received the credentials. Waiting for its Wi-Fi connection…',
    'connecting' => 'The Pi is connecting to the hotspot…',
    'connected' => 'The Pi reports connected. Reading its one-time secure handoff…',
    'failed' => 'The Pi reports that Wi-Fi setup failed.',
    'invalid' => 'The Pi rejected the Wi-Fi credentials.',
    'expired' => 'The Pi setup window expired. Hold the button for 3 seconds and retry.',
    'idle' => 'The Pi setup window is not active. Hold the button for 3 seconds and retry.',
    _ => 'Waiting for the Pi setup status…',
  };

  Future<void> _provisionHotspot() async {
    if (_provisioning) return;
    setState(() {
      _provisioning = true;
      _provisioningFailed = false;
      _provisioningMessage = 'Searching for Thashu over Bluetooth…';
    });
    try {
      final handoff = await _wifiProvisioningClient.provision(
        ssid: _hotspotSsidController.text,
        password: _hotspotPasswordController.text,
        onStatus: (status) {
          if (!mounted) return;
          setState(() => _provisioningMessage = _provisioningStatusMessage(status));
        },
      );
      if (!mounted) return;
      setState(() {
        _addressController.text = handoff.apiBaseUrl;
        _fingerprintController.text = handoff.serverCertSha256;
        _tokenController.text = handoff.apiToken;
        _provisioningMessage =
            'The Pi joined Wi-Fi. Review the connection details, then tap Save connection. No robot command was sent.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _provisioningFailed = true;
        _provisioningMessage = error.toString().replaceFirst('Bad state: ', '');
      });
    } finally {
      _hotspotSsidController.clear();
      _hotspotPasswordController.clear();
      if (mounted) setState(() => _provisioning = false);
    }
  }

  Future<void> _save() async {
    final callback = widget.onSaveConnectionWithPin;
    final legacyCallback = widget.onSaveConnection;
    if ((callback == null && legacyCallback == null) || _saving) return;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final message = callback != null
          ? await callback(
              _addressController.text,
              _tokenController.text,
              _fingerprintController.text,
            )
          : await legacyCallback!(
              _addressController.text,
              _tokenController.text,
            );
      if (!mounted) return;
      setState(() => _message = message);
      if (message == null ||
          (!message.startsWith('Could not') && !message.startsWith('Enter '))) {
        _tokenController.clear();
      }
    } catch (error) {
      if (mounted) setState(() => _message = 'Could not save connection: $error');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _clear() async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.onClearConnection?.call();
      if (!mounted) return;
      setState(() {
        _addressController.clear();
        _tokenController.clear();
        _fingerprintController.clear();
        _message = 'Saved Pi connection settings were removed from this phone.';
      });
    } catch (error) {
      if (mounted) setState(() => _message = 'Could not clear connection settings: $error');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _buildHotspotProvisioningCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Connect Thashu to this phone’s hotspot',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            const Text(
              'Turn on this phone’s hotspot. Enter its exact name and password, '
              'then hold the Pi setup button for 3 seconds. Tap Connect & send '
              'within the 60-second setup window.',
            ),
            const SizedBox(height: 12),
            TextField(
              key: const ValueKey('hotspot-ssid-field'),
              controller: _hotspotSsidController,
              enabled: !_provisioning,
              autocorrect: false,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Hotspot name (SSID)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey('hotspot-password-field'),
              controller: _hotspotPasswordController,
              enabled: !_provisioning,
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) async {
                if (!_provisioning) await _provisionHotspot();
              },
              decoration: const InputDecoration(
                labelText: 'Hotspot password',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              key: const ValueKey('provision-hotspot-button'),
              onPressed: _provisioning ? null : _provisionHotspot,
              icon: _provisioning
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.bluetooth_searching),
              label: Text(_provisioning ? 'Connecting…' : 'Connect & send'),
            ),
            if (_provisioningMessage != null) ...[
              const SizedBox(height: 10),
              Semantics(
                liveRegion: true,
                child: Text(
                  _provisioningMessage!,
                  style: TextStyle(
                    color: _provisioningFailed
                        ? Theme.of(context).colorScheme.error
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Text(
              'The Pi setup uses encrypted Bluetooth and its physical-button window. '
              'The current pairing design has no passkey, so it does not protect '
              'against an active nearby impersonation attack; security review is pending.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Text(
              'The password is sent over encrypted Bluetooth and cleared after the attempt. '
              'The Pi returns its HTTPS address, certificate pin, and token once '
              'it reports connected. Review them and tap Save; this sends no robot command.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Text('Settings', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        Text('Robot connection', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        _buildHotspotProvisioningCard(context),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  key: const ValueKey('pi-address-field'),
                  controller: _addressController,
                  enabled: !_saving && !widget.isLoading,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Pi API address',
                    hintText: 'https://<Pi Wi-Fi IPv4>:8443',
                    helperText: 'Use the Pi HTTPS address on the same Wi-Fi or phone hotspot.',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const ValueKey('pi-token-field'),
                  controller: _tokenController,
                  enabled: !_saving && !widget.isLoading,
                  obscureText: true,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: InputDecoration(
                    labelText: 'Bearer token',
                    hintText: widget.tokenConfigured
                        ? 'Saved securely; leave blank to keep it'
                        : 'Enter the Pi API token',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const ValueKey('pi-certificate-fingerprint-field'),
                  controller: _fingerprintController,
                  enabled: !_saving && !widget.isLoading,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: const InputDecoration(
                    labelText: 'Pi certificate SHA-256 fingerprint',
                    hintText: 'sha256: followed by 64 lowercase hex characters',
                    helperText: 'Required for the Pi local HTTPS listener on port 8443.',
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  key: const ValueKey('save-pi-connection-button'),
                  onPressed: _saving || widget.isLoading ? null : _save,
                  icon: _saving
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.lock_outline),
                  label: const Text('Save connection'),
                ),
                if (widget.tokenConfigured || widget.initialAddress != null)
                  TextButton.icon(
                    key: const ValueKey('clear-pi-connection-button'),
                    onPressed: _saving || widget.isLoading ? null : _clear,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Forget saved connection'),
                  ),
                if (_message != null) ...[
                  const SizedBox(height: 8),
                  Semantics(liveRegion: true, child: Text(_message!)),
                ],
                const SizedBox(height: 8),
                const Text(
                  'The app uses the Pi locally and does not need internet access. '
                  'The phone and Pi must be connected to the same Wi-Fi or hotspot. '
                  'Credentials stay on this phone in secure storage.',
                  style: TextStyle(fontSize: 12),
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
                const Text('1. Check connection and reported mode on Dashboard.'),
                const SizedBox(height: 6),
                const Text('2. Use the existing Manual Control screen for movement.'),
                const SizedBox(height: 6),
                const Text(
                  '3. Use normal STOP to request a stop. Emergency Stop is unavailable, '
                  'and an acknowledgement does not confirm the robot physically stopped.',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
