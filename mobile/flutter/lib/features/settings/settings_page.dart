import 'package:flutter/material.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({
    super.key,
    this.initialAddress,
    this.tokenConfigured = false,
    this.isLoading = false,
    this.onSaveConnection,
    this.onClearConnection,
    this.onOpenManualControl,
  });

  final String? initialAddress;
  final bool tokenConfigured;
  final bool isLoading;
  final Future<String?> Function(String address, String token)? onSaveConnection;
  final Future<void> Function()? onClearConnection;
  final VoidCallback? onOpenManualControl;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _addressController;
  final TextEditingController _tokenController = TextEditingController();
  bool _saving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _addressController = TextEditingController(text: widget.initialAddress ?? '');
  }

  @override
  void didUpdateWidget(covariant SettingsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialAddress != widget.initialAddress) {
      _addressController.text = widget.initialAddress ?? '';
    }
  }

  @override
  void dispose() {
    _addressController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final callback = widget.onSaveConnection;
    if (callback == null || _saving) return;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final message = await callback(
        _addressController.text,
        _tokenController.text,
      );
      if (!mounted) return;
      setState(() => _message = message);
      if (message == null || !message.startsWith('Could not') && !message.startsWith('Enter ')) {
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
        _message = 'Saved Pi connection settings were removed from this phone.';
      });
    } catch (error) {
      if (mounted) setState(() => _message = 'Could not clear connection settings: $error');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
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
                    hintText: 'https://thashu.local:8000',
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
