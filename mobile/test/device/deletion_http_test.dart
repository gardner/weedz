import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/deletion_http.dart';
import 'package:weedz/device/device_record.dart';

import 'fakes.dart' as fixtures;

void main() {
  final enrollment = DeviceEnrollment(
    server: 'https://intake.example.test/pilot/',
    token: 'weedzsub_12_${'a_' * 22}',
  );
  final completed = jsonEncode({
    'status': 'deleted',
    'requested_at': '2026-11-14T21:00:00+00:00',
    'completed_at': '2026-11-14T21:00:01+00:00',
  });

  test(
    'sends DELETE to the stored service without redirects or body',
    () async {
      final api = HttpDeleteSubmitter(
        client: MockClient((request) async {
          expect(
            request.url.toString(),
            'https://intake.example.test/pilot/submitter',
          );
          expect(request.method, 'DELETE');
          expect(
            request.headers['Authorization'],
            'Bearer ${enrollment.token}',
          );
          expect(request.followRedirects, isFalse);
          expect(request.body, isEmpty);
          return http.Response(completed, 200);
        }),
      );
      expect(
        (await api.delete(enrollment)).completedAt,
        DateTime.utc(2026, 11, 14, 21, 0, 1),
      );
    },
  );

  for (final status in [401, 302, 429, 500]) {
    test('$status is never proof of deletion', () async {
      final api = HttpDeleteSubmitter(
        client: MockClient((_) async => http.Response(completed, status)),
      );
      await expectLater(
        api.delete(enrollment),
        throwsA(isA<DeletionFailure>()),
      );
    });
  }

  final invalidBodies = [
    '{}',
    'not JSON',
    '{"status":"pending"}',
    jsonEncode({
      'status': 'deleted',
      'requested_at': '2026-11-14',
      'completed_at': '2026-11-14',
    }),
    jsonEncode({
      'status': 'deleted',
      'requested_at': '2026-11-14T21:00:00Z',
      'completed_at': null,
    }),
    jsonEncode({
      'status': 'deleted',
      'requested_at': '2026-02-30T21:00:00Z',
      'completed_at': '2026-11-14T21:00:00Z',
    }),
    jsonEncode({
      'status': 'deleted',
      'requested_at': '2026-11-14T21:00:01Z',
      'completed_at': '2026-11-14T21:00:00Z',
    }),
    'x' * 5000,
  ];
  for (final (index, body) in invalidBodies.indexed) {
    test('invalid 200 receipt $index cannot clear credentials', () async {
      final api = HttpDeleteSubmitter(
        client: MockClient((_) async => http.Response(body, 200)),
      );
      await expectLater(
        api.delete(enrollment),
        throwsA(isA<DeletionFailure>()),
      );
    });
  }

  test(
    'a revoked credential stays pending instead of claiming deletion',
    () async {
      final store = fixtures.MemoryStore();
      final controller = DeviceDeletion(
        store: store,
        api: HttpDeleteSubmitter(
          client: MockClient((_) async => http.Response('Unauthorized', 401)),
        ),
      );
      await controller.load();
      await controller.enroll(enrollment);
      await controller.delete();
      expect(controller.phase, DeletionPhase.pending);
      expect(controller.problem, DeletionProblem.unauthorized);
      expect(controller.canUpload, isFalse);
      expect(store.value, contains(enrollment.token));
    },
  );

  test('unanswered requests time out without a completion receipt', () async {
    final response = Completer<http.Response>();
    final api = HttpDeleteSubmitter(
      client: MockClient((_) => response.future),
      timeout: const Duration(milliseconds: 5),
    );
    await expectLater(api.delete(enrollment), throwsA(isA<DeletionFailure>()));
    response.complete(http.Response(completed, 200));
  });

  test('refuses insecure addresses and secrets in addresses', () {
    for (final address in [
      'http://intake.example.test',
      'https://user:secret@example.test',
      'https://example.test/?token=secret',
      'https://example.test/#secret',
    ]) {
      expect(() => intakeAddress(address), throwsFormatException);
    }
  });
}
