import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/report.dart';

import 'fixtures.dart';

void main() {
  final now = DateTime.utc(2026, 11, 14, 12);

  Report build(DateTime? capturedAt) {
    final base = minimalReport();
    return Report(
      appVersion: base.appVersion,
      candidate: base.candidate,
      model: base.model,
      consent: base.consent,
      capturedAt: capturedAt,
      clock: () => now,
    );
  }

  test('refuses capture times more than a day ahead before approval', () {
    expect(
      () => build(now.add(const Duration(days: 1, microseconds: 1))),
      throwsArgumentError,
    );
  });

  test('accepts the boundary, past captures and absent capture times', () {
    for (final captured in [
      now.add(const Duration(days: 1)),
      now,
      now.subtract(const Duration(days: 100)),
      null,
    ]) {
      expect(build(captured).capturedAt, captured);
    }
  });

  test('compares instants when capture time is in the local zone', () {
    expect(
      () => build(now.add(const Duration(days: 2)).toLocal()),
      throwsArgumentError,
    );
  });

  test('uses the device clock when no clock is injected', () {
    expect(
      () => minimalReport().copyWith(
        capturedAt: DateTime.now().add(const Duration(days: 2)),
      ),
      throwsArgumentError,
    );
  });
}
