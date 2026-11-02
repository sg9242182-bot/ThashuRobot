import 'package:flutter/material.dart';

import '../widgets/zeno_offline_notice.dart';

ThemeData buildZenoTheme() {
  final colorScheme = ColorScheme.fromSeed(seedColor: Colors.deepPurple);

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    textTheme: const TextTheme(
      titleLarge: TextStyle(fontWeight: FontWeight.w600),
      bodyLarge: TextStyle(fontSize: 16),
    ),
  );
}

class ZenoNavigationShell extends StatefulWidget {
  const ZenoNavigationShell({super.key});

  @override
  State<ZenoNavigationShell> createState() => _ZenoNavigationShellState();
}

class _ZenoNavigationShellState extends State<ZenoNavigationShell> {
  int _selectedIndex = 0;

  static const List<String> _titles = [
    'Dashboard',
    'Manual Control',
    'Settings',
    'Diagnostics',
    'Developer / Recovery',
  ];
  static const List<String> _placeholderMessages = [
    'Placeholder: Robot overview will appear here.',
    'Placeholder: Controls are unavailable until the Pi connection is ready.',
    'Placeholder: App and connection settings will appear here.',
    'Placeholder: Diagnostics will appear when data is available.',
    'Placeholder: Developer and recovery tools are not available yet.',
  ];
  static const List<IconData> _icons = [
    Icons.dashboard_outlined,
    Icons.gamepad_outlined,
    Icons.settings_outlined,
    Icons.monitor_heart_outlined,
    Icons.build_outlined,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ZENO controller')),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_icons[_selectedIndex], size: 48),
            const SizedBox(height: 12),
            Text(
              _titles[_selectedIndex],
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const ZenoOfflineNotice(),
            const SizedBox(height: 12),
            Text(
              _placeholderMessages[_selectedIndex],
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) {
          setState(() => _selectedIndex = index);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.gamepad_outlined),
            label: 'Manual Control',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            label: 'Settings',
          ),
          NavigationDestination(
            icon: Icon(Icons.monitor_heart_outlined),
            label: 'Diagnostics',
          ),
          NavigationDestination(
            icon: Icon(Icons.build_outlined),
            label: 'Developer / Recovery',
          ),
        ],
      ),
    );
  }
}
