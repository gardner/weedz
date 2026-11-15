import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/device/deletion.dart';

import 'fakes.dart';

void main() {
  test(
    'persists intent before request; confirmed receipt clears secret',
    () async {
      final store = MemoryStore();
      final api = FakeDeletion(store);
      final controller = DeviceDeletion(store: store, api: api);
      await controller.load();
      await controller.enroll(enrollment);
      expect(controller.canUpload, isTrue);
      await controller.delete();
      expect(controller.phase, DeletionPhase.deleted);
      expect(controller.canUpload, isFalse);
      expect(store.value, isNot(contains(enrollment.token)));
      expect(controller.completedAt, receipt.completedAt);
    },
  );

  test(
    'failed request retains token, stops uploads and resumes after restart',
    () async {
      final store = MemoryStore();
      final api = FakeDeletion(store)..fail = true;
      final first = DeviceDeletion(store: store, api: api);
      await first.load();
      await first.enroll(enrollment);
      await first.delete();
      expect(first.phase, DeletionPhase.pending);
      expect(first.canUpload, isFalse);
      expect(store.value, contains(enrollment.token));
      first.dispose();
      api.fail = false;
      final restarted = DeviceDeletion(store: store, api: api);
      await restarted.load();
      expect(api.calls, 2);
      expect(restarted.phase, DeletionPhase.deleted);
    },
  );

  test(
    'secure-storage failure never starts DELETE or claims completion',
    () async {
      final store = MemoryStore();
      final api = FakeDeletion(store);
      final controller = DeviceDeletion(store: store, api: api);
      await controller.load();
      await controller.enroll(enrollment);
      store.refuseWrites = true;
      await controller.delete();
      expect(api.calls, 0);
      expect(controller.phase, DeletionPhase.pending);
      expect(controller.canUpload, isFalse);
      expect(controller.problem, DeletionProblem.storage);
      expect(store.value, contains(enrollment.token));
    },
  );

  test(
    'completion write failure keeps pending credential for safe retry',
    () async {
      final store = MemoryStore();
      final api = FakeDeletion(store)..failCompletionSave = true;
      final controller = DeviceDeletion(store: store, api: api);
      await controller.load();
      await controller.enroll(enrollment);
      await controller.delete();
      expect(controller.phase, DeletionPhase.pending);
      expect(controller.problem, DeletionProblem.storage);
      expect(store.value, contains(enrollment.token));
    },
  );

  test(
    'corrupt secure record is not treated as unenrolled or erased',
    () async {
      final store = MemoryStore()..value = '{broken';
      final controller = DeviceDeletion(store: store, api: FakeDeletion(store));
      await controller.load();
      expect(controller.phase, DeletionPhase.unavailable);
      expect(controller.canUpload, isFalse);
      expect(store.value, '{broken');
    },
  );
}
