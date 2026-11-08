import 'package:flutter/material.dart';

class DeveloperRecoveryPage extends StatelessWidget {
  const DeveloperRecoveryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Text(
          'Developer / Recovery',
          style: Theme.of(context).textTheme.headlineSmall,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 16),
        const Card(
          child: ListTile(
            leading: Icon(Icons.build_outlined),
            title: Text('Recovery actions unavailable'),
            subtitle: Text('No approved recovery API is configured.'),
          ),
        ),
        const SizedBox(height: 8),
        const Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.lock_outline),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Reset and recovery controls stay hidden until their '
                    'behavior and authorization are approved by the backend '
                    'owner. This app provides no shell or direct hardware '
                    'commands.',
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
