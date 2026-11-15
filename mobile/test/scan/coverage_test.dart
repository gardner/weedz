import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/scan/coverage.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_index.dart';

ScanCoverage coverage({
  PhotoAccess access = PhotoAccess.full,
  int total = 5000,
  int screened = 1204,
  Map<SkipReason, int> skipped = const {},
}) => ScanCoverage(
  access: access,
  total: total,
  screened: screened,
  skipped: skipped,
);

void main() {
  group('Scan coverage', () {
    test('counts what is left to scan', () {
      final c = coverage(
        skipped: {SkipReason.cloudOnly: 30, SkipReason.tooSmall: 7},
      );
      expect(c.skippedTotal, 37);
      expect(c.remaining, 5000 - 1204 - 37);
      expect(c.isComplete, isFalse);
    });

    test('is complete when every photo is screened or skipped', () {
      final c = coverage(
        total: 10,
        screened: 8,
        skipped: {SkipReason.unsupported: 2},
      );
      expect(c.remaining, 0);
      expect(c.isComplete, isTrue);
    });

    test('never reports a negative remainder', () {
      expect(coverage(total: 3, screened: 5).remaining, 0);
    });

    test('says how much was scanned, with thousands separators', () {
      expect(coverage().describe(), 'Scanned 1,204 of 5,000 photos.');
    });

    test('says how many were skipped and why, largest reason first', () {
      final c = coverage(
        skipped: {SkipReason.tooSmall: 7, SkipReason.cloudOnly: 30},
      );
      expect(
        c.describe(),
        'Scanned 1,204 of 5,000 photos. '
        '37 skipped: 30 are stored only in the cloud, '
        '7 are too small to check.',
      );
    });

    test('words a single photo in the singular', () {
      final c = coverage(
        total: 1,
        screened: 0,
        skipped: {SkipReason.unreadable: 1},
      );
      expect(
        c.describe(),
        'Scanned 0 of 1 photo. 1 skipped: 1 could not be opened.',
      );
    });

    test('names every skip reason in plain words', () {
      for (final reason in SkipReason.values) {
        expect(reason.explanation, isNotEmpty);
      }
      expect(SkipReason.unsupported.explanation, contains('format'));
    });

    test('says when it covers only the chosen photos', () {
      final c = coverage(access: PhotoAccess.limited, total: 40, screened: 40);
      expect(
        c.describe(),
        'Scanned 40 of 40 photos. '
        'This covers only the photos you chose to share.',
      );
    });

    test('asks for access when it cannot see the library', () {
      final c = coverage(access: PhotoAccess.denied, total: 0, screened: 0);
      expect(c.describe(), PhotoAccess.denied.coverageNote);
    });
  });
}
