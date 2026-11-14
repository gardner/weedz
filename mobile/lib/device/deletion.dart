/// Restartable device deletion. Never infer success from authentication
/// failure.
library;

import 'package:flutter/foundation.dart';
import 'package:weedz/device/device_record.dart';

export 'package:weedz/device/device_record.dart' show DeletionReceipt;

abstract interface class DeleteSubmitter {
  Future<DeletionReceipt> delete(DeviceEnrollment device);
  void close();
}

enum DeletionPhase { loading, unenrolled, ready, pending, deleted, unavailable }

enum DeletionProblem { storage, unconfirmed, unauthorized }

final class DeletionFailure implements Exception {
  const new(this.problem);
  final DeletionProblem problem;
}

/// Upload workers must use [canUpload] before starting/retrying an upload.
/// There is no upload worker yet; deletion permanently blocks this enrollment.
final class DeviceDeletion extends ChangeNotifier {
  new({required this._store, required this._api});

  final DeviceRecordStore _store;
  final DeleteSubmitter _api;
  DeviceRecord? _record;
  bool _disposed = false;
  bool busy = false;
  DeletionPhase phase = DeletionPhase.loading;
  DeletionProblem? problem;

  bool get canUpload => phase == DeletionPhase.ready && !busy;
  String? get server => _record?.device?.server.toString();
  DateTime? get completedAt => _record?.completedAt;

  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    if (busy) return;
    busy = true;
    problem = null;
    try {
      final text = await _store.read();
      _record = text == null ? null : DeviceRecord.parse(text);
      phase = switch (_record) {
        null => DeletionPhase.unenrolled,
        DeviceRecord(device: null) => DeletionPhase.deleted,
        DeviceRecord(pending: true) => DeletionPhase.pending,
        _ => DeletionPhase.ready,
      };
    } on Exception {
      phase = DeletionPhase.unavailable;
      problem = DeletionProblem.storage;
    } finally {
      busy = false;
      _changed();
    }
    if (phase == DeletionPhase.pending) await delete();
  }

  Future<void> enroll(DeviceEnrollment device) async {
    if (busy ||
        (phase != DeletionPhase.unenrolled && phase != DeletionPhase.deleted)) {
      return;
    }
    busy = true;
    problem = null;
    _changed();
    final record = DeviceRecord(device: device);
    try {
      await _store.write(record.encode());
      _record = record;
      phase = DeletionPhase.ready;
    } on Exception {
      phase = DeletionPhase.unavailable;
      problem = DeletionProblem.storage;
    } finally {
      busy = false;
      _changed();
    }
  }

  Future<void> delete() async {
    if (busy ||
        (phase != DeletionPhase.ready && phase != DeletionPhase.pending)) {
      return;
    }
    final device = _record!.device!;
    busy = true;
    problem = null;
    _changed();
    // Commit intent first. Failure leaves the previous secure record intact.
    final pending = DeviceRecord(device: device, pending: true);
    _record = pending;
    phase = DeletionPhase.pending;
    _changed();
    try {
      await _store.write(pending.encode());
    } on Exception {
      problem = DeletionProblem.storage;
      busy = false;
      _changed();
      return;
    }
    _changed();
    try {
      final receipt = await _api.delete(device);
      final completed = DeviceRecord(
        device: null,
        completedAt: receipt.completedAt,
      );
      // Replace the entire record atomically; no separate token/intent
      // deletion.
      try {
        await _store.write(completed.encode());
        _record = completed;
        phase = DeletionPhase.deleted;
      } on Exception {
        problem = DeletionProblem.storage;
      }
    } on DeletionFailure catch (error) {
      problem = error.problem;
    } on Exception {
      problem = DeletionProblem.unconfirmed;
    } finally {
      busy = false;
      _changed();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _api.close();
    super.dispose();
  }
}
