import 'package:flutter/material.dart';

import '../features/dashboard/dashboard_page.dart';
import '../services/pi_api_client.dart';
import '../widgets/zeno_offline_notice.dart';

ThemeData buildZenoTheme() {
  final colorScheme = ColorScheme.fromSeed(seedColor: Colors.deepPurple);

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    navigationBarTheme: const NavigationBarThemeData(
      labelTextStyle: WidgetStatePropertyAll(TextStyle(fontSize: 11)),
    ),
    textTheme: const TextTheme(
      titleLarge: TextStyle(fontWeight: FontWeight.w600),
      bodyLarge: TextStyle(fontSize: 16),
    ),
  );
}

class ZenoNavigationShell extends StatefulWidget {
  const ZenoNavigationShell({super.key, this.apiClient});

  final PiApiClient? apiClient;

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
      body: _selectedIndex == 0
          ? DashboardPage(apiClient: widget.apiClient)
          : Center(
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
      bottomNavigationBar: SafeArea(
        top: false,
        child: SizedBox(
          height: 100,
          child: Row(
            children: List.generate(_titles.length, (index) {
              return Expanded(
                child: Transform.translate(
                  offset: Offset(0, 0),
                  child: SizedBox.expand(
                    child: InkWell(
                      key: ValueKey('nav-destination-$index'),
                      onTap: () => setState(() => _selectedIndex = index),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: _selectedIndex == index
                                  ? Theme.of(context)
                                        .colorScheme
                                        .secondaryContainer
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(24),
                            ),
                            child: Icon(_icons[index]),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            _titles[index],
                            textAlign: TextAlign.center,
                            maxLines: 3,
                            style: const TextStyle(fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
