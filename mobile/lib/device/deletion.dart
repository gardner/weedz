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
  bool _busy = false;
  DeletionPhase _phase = DeletionPhase.loading;
  DeletionProblem? _problem;

  bool get busy => _busy;
  DeletionPhase get phase => _phase;
  DeletionProblem? get problem => _problem;

  bool get canUpload => _phase == DeletionPhase.ready && !_busy;
  String? get server => _record?.device?.server.toString();
  DateTime? get completedAt => _record?.completedAt;

  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    if (_busy) return;
    _busy = true;
    _problem = null;
    try {
      final text = await _store.read();
      _record = text == null ? null : DeviceRecord.parse(text);
      _phase = switch (_record) {
        null => DeletionPhase.unenrolled,
        DeviceRecord(device: null) => DeletionPhase.deleted,
        DeviceRecord(pending: true) => DeletionPhase.pending,
        _ => DeletionPhase.ready,
      };
    } on Exception {
      _phase = DeletionPhase.unavailable;
      _problem = DeletionProblem.storage;
    } finally {
      _busy = false;
      _changed();
    }
    if (_phase == DeletionPhase.pending) await delete();
  }

  Future<void> enroll(DeviceEnrollment device) async {
    if (_busy ||
        (_phase != DeletionPhase.unenrolled &&
            _phase != DeletionPhase.deleted)) {
      return;
    }
    _busy = true;
    _problem = null;
    _changed();
    final record = DeviceRecord(device: device);
    try {
      await _store.write(record.encode());
      _record = record;
      _phase = DeletionPhase.ready;
    } on Exception {
      _phase = DeletionPhase.unavailable;
      _problem = DeletionProblem.storage;
    } finally {
      _busy = false;
      _changed();
    }
  }

  Future<void> delete() async {
    if (_busy ||
        (_phase != DeletionPhase.ready && _phase != DeletionPhase.pending)) {
      return;
    }
    final device = _record!.device!;
    _busy = true;
    _problem = null;
    _changed();
    // Commit intent first. Failure leaves the previous secure record intact.
    final pending = DeviceRecord(device: device, pending: true);
    _record = pending;
    _phase = DeletionPhase.pending;
    _changed();
    try {
      await _store.write(pending.encode());
    } on Exception {
      _problem = DeletionProblem.storage;
      _busy = false;
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
        _phase = DeletionPhase.deleted;
      } on Exception {
        _problem = DeletionProblem.storage;
      }
    } on DeletionFailure catch (error) {
      _problem = error.problem;
    } on Exception {
      _problem = DeletionProblem.unconfirmed;
    } finally {
      _busy = false;
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
