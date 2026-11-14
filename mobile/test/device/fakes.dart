import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/device_record.dart';

final receipt = DeletionReceipt.parse(
  jsonEncode({
    'status': 'deleted',
    'requested_at': '2026-11-14T21:00:00Z',
    'completed_at': '2026-11-14T21:00:01Z',
  }),
);

final enrollment = DeviceEnrollment(
  server: 'https://intake.example.test/pilot/',
  token: 'weedzsub_1_${'a' * 43}',
);

class MemoryStore implements DeviceRecordStore {
  String? value;
  bool refuseWrites = false;

  @override
  Future<String?> read() async => value;

  @override
  Future<void> write(String record) async {
    if (refuseWrites) throw Exception('secure store unavailable');
    value = record;
  }
}

class FakeDeletion implements DeleteSubmitter {
  new(this.store);
  final MemoryStore store;
  int calls = 0;
  bool fail = false;
  bool failCompletionSave = false;

  @override
  Future<DeletionReceipt> delete(DeviceEnrollment device) async {
    calls++;
    final saved = jsonDecode(store.value!) as Map<String, dynamic>;
    expect(saved['pending'], isTrue);
    expect(device.token, enrollment.token);
    if (fail) throw const DeletionFailure(DeletionProblem.unconfirmed);
    if (failCompletionSave) store.refuseWrites = true;
    return receipt;
  }

  @override
  void close() {}
}
