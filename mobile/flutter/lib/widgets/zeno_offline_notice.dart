import 'package:flutter/material.dart';

enum ZenoNoticeState { loading, empty, offline, unavailable, error }

class ZenoOfflineNotice extends StatelessWidget {
  const ZenoOfflineNotice({super.key, this.state = ZenoNoticeState.offline});

  final ZenoNoticeState state;

  String get _message {
    switch (state) {
      case ZenoNoticeState.loading:
        return 'Loading robot information…';
      case ZenoNoticeState.empty:
        return 'No robot data is available yet.';
      case ZenoNoticeState.offline:
        return 'Pi is not connected. Robot data and controls are unavailable.';
      case ZenoNoticeState.unavailable:
        return 'This feature is currently unavailable.';
      case ZenoNoticeState.error:
        return 'Could not load robot information.';
    }
  }

  IconData get _icon {
    switch (state) {
      case ZenoNoticeState.loading:
        return Icons.hourglass_empty;
      case ZenoNoticeState.empty:
        return Icons.inbox_outlined;
      case ZenoNoticeState.offline:
        return Icons.cloud_off_outlined;
      case ZenoNoticeState.unavailable:
        return Icons.block_outlined;
      case ZenoNoticeState.error:
        return Icons.error_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon),
          const SizedBox(width: 12),
          Flexible(child: Text(_message)),
        ],
      ),
    );
  }
}
