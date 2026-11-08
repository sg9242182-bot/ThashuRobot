import 'package:flutter/material.dart';

import 'app/app.dart';
import 'services/pi_api_client.dart';
import 'services/pi_telemetry_client.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key, this.apiClient, this.telemetryClient});

  final PiApiClient? apiClient;
  final PiTelemetryClient? telemetryClient;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ZENO controller',
      debugShowCheckedModeBanner: false,
      theme: buildZenoTheme(),
      home: ZenoNavigationShell(
        apiClient: apiClient,
        telemetryClient: telemetryClient,
      ),
    );
  }
}
