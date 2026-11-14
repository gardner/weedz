import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/metadata/capture_time.dart';

void main() {
  group('Offset known: DateTimeOriginal with OffsetTimeOriginal', () {
    test('is an exact instant, sent in UTC', () {
      final time = captureTime('2026:10:03 12:15:42', '+13:00');
      expect(time, isA<OffsetKnownTime>());
      final known = time as OffsetKnownTime;
      expect(known.instant, DateTime.utc(2026, 10, 2, 23, 15, 42));
      expect(known.instant.isUtc, isTrue);
      expect(known.offset, const Duration(hours: 13));
      expect(time.reportCapturedAt, DateTime.utc(2026, 10, 2, 23, 15, 42));
    });

    test('handles negative and half-hour offsets', () {
      final time = captureTime('2026:01:01 00:10:00', '-03:30') as OffsetKnownTime;
      expect(time.instant, DateTime.utc(2026, 1, 1, 3, 40));
      expect(time.offset, const Duration(hours: -3, minutes: -30));
    });

    test('tolerates the NUL and space padding EXIF strings carry', () {
      final time = captureTime('2026:10:03 12:15:42\u0000', ' +13:00\u0000');
      expect(time, isA<OffsetKnownTime>());
    });
  });

  group('Local only: no time zone', () {
    test('keeps the wall-clock time but sends no capture time', () {
      final time = captureTime('2026:10:03 12:15:42', null);
      expect(time, isA<LocalOnlyTime>());
      expect(
        (time as LocalOnlyTime).wallClock,
        DateTime.utc(2026, 10, 3, 12, 15, 42),
      );
      expect(time.reportCapturedAt, isNull);
    });

    test('when the offset is blank or malformed', () {
      for (final offset in ['', '   :  ', '+1300', '+15:00', '+13:60', 'Z']) {
        expect(
          captureTime('2026:10:03 12:15:42', offset),
          isA<LocalOnlyTime>(),
          reason: offset,
        );
      }
    });
  });

  group('Missing', () {
    test('when DateTimeOriginal is absent, blank or malformed', () {
      for (final value in [
        null,
        '',
        '0000:00:00 00:00:00',
        '    :  :     :  :  ',
        '2026:13:01 00:00:00',
        '2026:02:30 00:00:00',
        '2026:10:03 24:00:00',
        '2026-10-03T12:15:42',
      ]) {
        final time = captureTime(value, '+13:00');
        expect(time, isA<MissingTime>(), reason: value);
        expect(time.reportCapturedAt, isNull);
      }
    });
  });

  group('GPS time', () {
    test('parses GPSDateStamp and GPSTimeStamp as UTC', () {
      expect(
        gpsTime('2026:10:02', '23:15:41.50'),
        DateTime.utc(2026, 10, 2, 23, 15, 41, 500),
      );
      expect(gpsTime('2026:10:02', '23:15:41'), isNotNull);
    });

    test('is absent when either part is missing or malformed', () {
      expect(gpsTime(null, '23:15:41'), isNull);
      expect(gpsTime('2026:10:02', null), isNull);
      expect(gpsTime('2026:10:02', '25:00:00'), isNull);
      expect(gpsTime('0000:00:00', '00:00:00'), isNull);
    });
  });

  group('GPS-time cross-check', () {
    final known = captureTime('2026:10:03 12:15:42', '+13:00');

    test('agrees when the fix was taken at the capture time', () {
      final check = checkGpsTime(known, DateTime.utc(2026, 10, 2, 23, 15, 41));
      expect(check, isA<GpsTimeAgrees>());
    });

    test('agrees at the tolerance and disagrees beyond it', () {
      final capture = DateTime.utc(2026, 10, 2, 23, 15, 42);
      expect(
        checkGpsTime(known, capture.add(gpsTimeTolerance)),
        isA<GpsTimeAgrees>(),
      );
      final late = checkGpsTime(
        known,
        capture.subtract(gpsTimeTolerance + const Duration(seconds: 1)),
      );
      expect(late, isA<GpsTimeDisagrees>());
    });

    test('says by how much a stale fix or a wrong clock disagrees', () {
      final stale = DateTime.utc(2026, 10, 2, 22, 15, 42);
      final check = checkGpsTime(known, stale) as GpsTimeDisagrees;
      expect(check.by, const Duration(hours: 1));
    });

    test('is unavailable without a GPS time or an exact capture time', () {
      final fix = DateTime.utc(2026, 10, 2, 23, 15, 41);
      expect(checkGpsTime(known, null), isA<GpsTimeUnavailable>());
      expect(
        checkGpsTime(captureTime('2026:10:03 12:15:42', null), fix),
        isA<GpsTimeUnavailable>(),
      );
      expect(
        checkGpsTime(captureTime(null, null), fix),
        isA<GpsTimeUnavailable>(),
      );
    });
  });
}
