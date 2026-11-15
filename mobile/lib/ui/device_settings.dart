import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/deletion_http.dart';
import 'package:weedz/device/deployment.dart';
import 'package:weedz/device/secure_record_store.dart';
import 'package:weedz/ui/device_enrollment.dart';

const _retained =
    'Deletes this enrollment’s reports and crops from the intake and revokes '
    'its access. Report and deletion IDs and times, and credential hash, '
    'operator label and issue/revocation times remain. Independent backups, '
    'exports, downstream copies and trained models are not recalled. Your '
    'photo-library originals are never deleted.';

/// The settings action is connected to the real authenticated deletion
/// operation.
class DeviceSettings extends StatefulWidget {
  const new({
    this.controller,
    this.deployment = const DeviceDeployment(),
    this.openRoute,
    super.key,
  });

  final DeviceDeletion? controller;
  final DeviceDeployment deployment;
  final Future<bool> Function(Uri)? openRoute;

  @override
  State<DeviceSettings> createState() => _DeviceSettingsState();
}

class _DeviceSettingsState extends State<DeviceSettings> {
  late final DeviceDeletion _controller =
      widget.controller ??
      DeviceDeletion(
        store: const SecureDeviceRecordStore(),
        api: HttpDeleteSubmitter(),
      );
  String? _routeError;

  @override
  void initState() {
    super.initState();
    unawaited(_controller.load());
  }

  @override
  void dispose() {
    if (widget.controller == null) _controller.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete all reports from this phone?'),
        content: const SingleChildScrollView(child: Text(_retained)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep my data'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete reports and revoke access'),
          ),
        ],
      ),
    );
    if (confirmed ?? false) await _controller.delete();
  }

  Future<void> _openPublicRoute(Uri route) async {
    var opened = false;
    try {
      opened =
          await (widget.openRoute?.call(route) ??
              launchUrl(route, mode: LaunchMode.externalApplication));
    } on Exception {
      // Platform errors must not expose URLs containing unexpected private
      // values.
    }
    if (mounted) {
      setState(
        () => _routeError = opened
            ? null
            : 'Could not open the public deletion request page. Try again.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Settings')),
    body: SafeArea(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.all(24),
          children: [
            ..._content(),
            const SizedBox(height: 16),
            const ExpansionTile(
              tilePadding: EdgeInsets.zero,
              key: ValueKey('retention'),
              title: Text('What deletion removes'),
              children: [
                Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: Text(_retained),
                ),
              ],
            ),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              key: const ValueKey('help'),
              title: const Text('Help'),
              children: [
                if (widget.deployment.publicDeletionRoute case final route?)
                  OutlinedButton(
                    onPressed: () => _openPublicRoute(route),
                    child: const Text('Request deletion without this phone'),
                  ),
                const Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: Text(
                    'If your token is lost or no longer works, contact the '
                    'operator who enrolled you. They will verify ownership '
                    'before deleting data. Never send your token by email '
                    'or through a public request form.',
                  ),
                ),
              ],
            ),
            if (_routeError case final error?) Text(error),
          ],
        ),
      ),
    ),
  );

  List<Widget> _content() {
    final controller = _controller;
    final message = switch (controller.phase) {
      DeletionPhase.loading => 'Reading secure enrollment…',
      DeletionPhase.unenrolled => 'This app has no saved enrollment.',
      DeletionPhase.ready => 'Enrollment saved',
      DeletionPhase.pending =>
        controller.busy ? 'Requesting deletion…' : 'Deletion not yet confirmed',
      DeletionPhase.deleted => 'Deletion confirmed',
      DeletionPhase.unavailable =>
        'Secure enrollment could not be read. No deletion is confirmed. '
            'Unlock your phone and retry; existing credentials have not been '
            'intentionally removed.',
    };
    return [
      Semantics(
        liveRegion: true,
        child: Text(message, style: const TextStyle(fontSize: 20)),
      ),
      if (controller.completedAt case final completed?)
        Text('Confirmed at ${completed.toLocal()}'),
      if (controller.busy) const LinearProgressIndicator(),
      if (controller.problem case final problem?)
        Text(switch (problem) {
          DeletionProblem.storage =>
            'Secure storage could not be updated. Keep this installation and '
                'retry; deletion is not yet confirmed here.',
          DeletionProblem.unauthorized =>
            'The server did not authorize deletion. Your token is retained. '
                'A separately revoked token needs the verified '
                'operator request route.',
          DeletionProblem.unconfirmed =>
            'No valid completion receipt arrived. Your token and deletion '
                'request are retained so you can retry. Reopen Settings to '
                'resume after a restart.',
        }),
      if (controller.phase == DeletionPhase.ready) ...[
        const SizedBox(height: 12),
        const Text(
          'Delete your shared sightings. Originals stay on your phone.',
        ),
        const SizedBox(height: 20),
        FilledButton(
          onPressed: controller.busy ? null : _confirm,
          child: const Text('Delete my data'),
        ),
      ],
      if (controller.server case final server?)
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          key: const ValueKey('connection'),
          title: const Text('Connection details'),
          children: [
            Text('Intake: $server'),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text(
                'Saved on this phone. Access is checked when a request '
                'is sent.',
              ),
            ),
          ],
        ),
      if (controller.phase == DeletionPhase.pending)
        FilledButton(
          onPressed: controller.busy ? null : controller.delete,
          child: const Text('Retry deletion'),
        ),
      if (controller.phase == DeletionPhase.unavailable)
        FilledButton(
          onPressed: controller.busy ? null : controller.load,
          child: const Text('Retry reading enrollment'),
        ),
      if (controller.phase == DeletionPhase.unenrolled ||
          controller.phase == DeletionPhase.deleted) ...[
        const SizedBox(height: 24),
        if (controller.phase == DeletionPhase.deleted)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            key: const ValueKey('reenrollment'),
            title: const Text('Set up another enrollment'),
            children: [
              DeviceEnrollmentForm(
                controller: controller,
                initialAddress: widget.deployment.enrollmentAddress,
              ),
            ],
          )
        else
          DeviceEnrollmentForm(
            controller: controller,
            initialAddress: widget.deployment.enrollmentAddress,
          ),
      ],
    ];
  }
}
