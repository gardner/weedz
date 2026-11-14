import 'package:flutter_test/flutter_test.dart';
import 'package:photo_manager/photo_manager.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/photo_manager_library.dart';

void main() {
  group('Photo access', () {
    test('full access scans the whole library and needs no note', () {
      expect(PhotoAccess.full.canScan, isTrue);
      expect(PhotoAccess.full.isPartial, isFalse);
      expect(PhotoAccess.full.coverageNote, isNull);
    });

    test('limited access scans only the chosen photos, and says so', () {
      expect(PhotoAccess.limited.canScan, isTrue);
      expect(PhotoAccess.limited.isPartial, isTrue);
      expect(
        PhotoAccess.limited.coverageNote,
        'This covers only the photos you chose to share.',
      );
    });

    test('denied access scans nothing, and asks for access', () {
      expect(PhotoAccess.denied.canScan, isFalse);
      expect(PhotoAccess.denied.isPartial, isFalse);
      expect(PhotoAccess.denied.coverageNote, contains('Allow photo access'));
    });
  });

  group("photo_manager's permission states", () {
    test('map onto full, limited and denied', () {
      expect(accessFrom(PermissionState.authorized), PhotoAccess.full);
      expect(accessFrom(PermissionState.limited), PhotoAccess.limited);
      expect(accessFrom(PermissionState.denied), PhotoAccess.denied);
    });

    test('treat restricted and not-yet-asked as denied for scanning', () {
      expect(accessFrom(PermissionState.restricted), PhotoAccess.denied);
      expect(accessFrom(PermissionState.notDetermined), PhotoAccess.denied);
    });
  });
}
