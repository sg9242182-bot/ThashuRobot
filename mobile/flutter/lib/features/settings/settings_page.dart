import 'package:flutter/material.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key, this.onOpenManualControl});

  final VoidCallback? onOpenManualControl;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Text('Settings', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.settings_outlined),
            title: const Text('Robot connection settings'),
            subtitle: const Text('Not available in this build'),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Text(
            'No API-approved connection fields are available to configure. '
            'The Pi address and token have not been provided, so this app '
            'does not save or display connection credentials.',
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
                  onPressed: onOpenManualControl,
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
