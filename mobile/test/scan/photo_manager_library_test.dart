import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/scan/photo_manager_library.dart';

void main() {
  group('The image handed to the screener', () {
    test('keeps the whole photo, scaled so its longer side fits', () {
      final landscape = screeningSize(
        width: 4032,
        height: 3024,
        longSide: 1024,
      );
      expect((landscape.width, landscape.height), (1024, 768));
      final portrait = screeningSize(width: 3024, height: 4032, longSide: 1024);
      expect((portrait.width, portrait.height), (768, 1024));
      final panorama = screeningSize(
        width: 12000,
        height: 3000,
        longSide: 1024,
      );
      expect((panorama.width, panorama.height), (1024, 256));
    });

    test('is never scaled up', () {
      final small = screeningSize(width: 800, height: 600, longSide: 1024);
      expect((small.width, small.height), (800, 600));
    });
  });

  group('On Android, the capture time photo_manager reports', () {
    test('is date_added before Android 10', () {
      expect(androidCaptureSeconds(sdkInt: 28), 'date_added');
    });

    test('is datetaken in seconds from Android 10, else date_added', () {
      final expression = androidCaptureSeconds(sdkInt: 29);
      expect(expression, contains('datetaken'));
      expect(expression, contains('date_added'));
    });

    test('is what the range filter compares, in whole seconds', () {
      const t = 'date_added';
      final second = DateTime.utc(2026, 11, 14, 12);
      final seconds = second.millisecondsSinceEpoch ~/ 1000;
      expect(androidCaptureWhere(t), '');
      expect(
        androidCaptureWhere(
          t,
          newest: second.add(const Duration(milliseconds: 999)),
        ),
        '$t <= $seconds',
      );
      expect(
        androidCaptureWhere(
          t,
          oldest: second.add(const Duration(milliseconds: 1)),
        ),
        '$t >= ${seconds + 1}',
      );
      expect(
        androidCaptureWhere(t, newest: second, oldest: second),
        '$t <= $seconds AND $t >= $seconds',
      );
    });
  });
}
