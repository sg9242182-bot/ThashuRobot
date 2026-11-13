import 'dart:async';

import 'package:flutter/material.dart';

import '../features/dashboard/dashboard_page.dart';
import '../features/developer/developer_recovery_page.dart';
import '../features/diagnostics/telemetry_diagnostics_page.dart';
import '../features/manual_control/manual_control_page.dart';
import '../features/settings/settings_page.dart';
import '../services/pi_api_client.dart';
import '../services/pi_connection_settings.dart';
import '../services/pi_telemetry_client.dart';
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
  const ZenoNavigationShell({super.key, this.apiClient, this.telemetryClient});

  final PiApiClient? apiClient;
  final PiTelemetryClient? telemetryClient;

  @override
  State<ZenoNavigationShell> createState() => _ZenoNavigationShellState();
}

class _ZenoNavigationShellState extends State<ZenoNavigationShell> {
  int _selectedIndex = 0;
  bool _manualControlVisited = false;
  final PiConnectionSettings _settings = PiConnectionSettings();
  late PiApiClient? _apiClient = widget.apiClient;
  late PiTelemetryClient? _telemetryClient = widget.telemetryClient;
  String? _connectionAddress;
  String? _connectionCertificateFingerprint;
  bool _tokenConfigured = false;
  bool _ownsClients = false;
  bool _loadingSettings = false;

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
  void initState() {
    super.initState();
    if (widget.apiClient == null) unawaited(_loadConnection());
  }

  Future<void> _loadConnection() async {
    if (mounted) setState(() => _loadingSettings = true);
    try {
      final address = await _settings.readAddress();
      final token = await _settings.readToken();
      final certificatePin = await _settings.readCertificatePin();
      if (address != null &&
          address.isNotEmpty &&
          token != null &&
          token.isNotEmpty) {
        final uri = Uri.parse(address);
        final api = PiApiClient(
          baseUri: uri,
          bearerToken: token,
          certificateSha256Fingerprint: certificatePin,
        );
        final telemetry = PiTelemetryClient(
          baseUri: uri,
          bearerToken: token,
          certificateSha256Fingerprint: certificatePin,
        );
        if (!mounted) {
          api.close();
          unawaited(telemetry.dispose());
          return;
        }
        setState(() {
          _connectionAddress = address;
          _connectionCertificateFingerprint = certificatePin;
          _tokenConfigured = true;
          _apiClient = api;
          _telemetryClient = telemetry;
          _ownsClients = true;
        });
      } else if (mounted) {
        setState(() {
          _connectionAddress = address;
          _connectionCertificateFingerprint = certificatePin;
          _tokenConfigured = token?.isNotEmpty ?? false;
        });
      }
    } catch (_) {
      // Keep the app offline if secure settings are unavailable or malformed.
    } finally {
      if (mounted) setState(() => _loadingSettings = false);
    }
  }

  Future<String?> _saveConnection(
    String address,
    String token,
    String certificateFingerprint,
  ) async {
    try {
      final existingToken = await _settings.readToken();
      final existingAddress = await _settings.readAddress();
      final existingPin = await _settings.readCertificatePin();
      final effectiveToken = token.trim().isEmpty
          ? existingToken
          : token.trim();
      if (effectiveToken == null || effectiveToken.isEmpty) {
        return 'Enter the Pi Bearer token before saving.';
      }

      final normalizedAddress = address.trim().replaceFirst(RegExp(r'/+$'), '');
      final sameAddress =
          existingAddress?.trim().replaceFirst(RegExp(r'/+$'), '') ==
          normalizedAddress;
      final effectivePin = certificateFingerprint.trim().isNotEmpty
          ? certificateFingerprint.trim()
          : (sameAddress ? existingPin : null);
      await _settings.save(
        baseUrl: normalizedAddress,
        bearerToken: token,
        certificateSha256Fingerprint: effectivePin,
      );
      final uri = Uri.parse(normalizedAddress);
      final api = PiApiClient(
        baseUri: uri,
        bearerToken: effectiveToken,
        certificateSha256Fingerprint: effectivePin,
      );
      final telemetry = PiTelemetryClient(
        baseUri: uri,
        bearerToken: effectiveToken,
        certificateSha256Fingerprint: effectivePin,
      );
      _disposeOwnedClients();

      if (!mounted) {
        api.close();
        unawaited(telemetry.dispose());
        return 'Settings saved securely.';
      }
      setState(() {
        _connectionAddress = uri.toString();
        _connectionCertificateFingerprint = effectivePin;
        _tokenConfigured = true;
        _apiClient = api;
        _telemetryClient = telemetry;
        _ownsClients = true;
      });
      return 'Saved securely. Check Dashboard and Diagnostics to verify the Pi connection. No robot command was sent.';
    } catch (error) {
      return 'Could not save connection settings: $error';
    }
  }

  Future<void> _clearConnection() async {
    await _settings.clear();
    _disposeOwnedClients();
    if (!mounted) return;
    setState(() {
      _connectionAddress = null;
      _connectionCertificateFingerprint = null;
      _tokenConfigured = false;
      _apiClient = widget.apiClient;
      _telemetryClient = widget.telemetryClient;
      _ownsClients = false;
    });
  }

  void _disposeOwnedClients() {
    if (!_ownsClients) return;
    _apiClient?.close();
    final telemetry = _telemetryClient;
    if (telemetry != null) unawaited(telemetry.dispose());
    _ownsClients = false;
  }

  void _selectPage(int index) {
    setState(() {
      _selectedIndex = index;
      if (index == 1) _manualControlVisited = true;
    });
  }

  Widget _buildSelectedPage() => switch (_selectedIndex) {
    0 => DashboardPage(apiClient: _apiClient),
    2 => SettingsPage(
      initialAddress: _connectionAddress,
      initialCertificateFingerprint: _connectionCertificateFingerprint,
      tokenConfigured: _tokenConfigured,
      isLoading: _loadingSettings,
      onSaveConnectionWithPin: _saveConnection,
      onClearConnection: _clearConnection,
      onOpenManualControl: () => _selectPage(1),
    ),
    3 => TelemetryDiagnosticsPage(
      client: _telemetryClient,
      apiClient: _apiClient,
    ),
    4 => const DeveloperRecoveryPage(),
    _ => Center(
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
  };

  @override
  void dispose() {
    _disposeOwnedClients();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Thashu Controller')),
      body: Stack(
        children: [
          if (_selectedIndex != 1) _buildSelectedPage(),
          if (_manualControlVisited)
            Offstage(
              offstage: _selectedIndex != 1,
              child: ManualControlPage(
                key: const ValueKey('manual-control-page'),
                apiClient: _apiClient,
                telemetryClient: _telemetryClient,
              ),
            ),
        ],
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
                      onTap: () => _selectPage(index),
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
