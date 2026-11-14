import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/metadata/photo_location.dart';
import 'package:weedz/metadata/raw_photo_metadata.dart';

import 'raw.dart';

void main() {
  group('Exact, with a stated accuracy', () {
    test('keeps full-precision coordinates and GPSHPositioningError', () {
      final location = photoLocation(iphonePhoto());
      expect(location, isA<ExactLocation>());
      expect(
        location.reportLocation,
        Location(latitude: -41.2706319, longitude: 173.2839653, accuracyM: 4.7),
      );
    });

    test('falls back to the platform accuracy when EXIF has none', () {
      final location = photoLocation(
        iphonePhoto(gpsHPositioningErrorM: null, platformAccuracyM: 12),
      );
      expect(location.reportLocation?.accuracyM, 12);
    });

    test('prefers the accuracy the camera wrote over the platform one', () {
      final location = photoLocation(iphonePhoto(platformAccuracyM: 30));
      expect(location.reportLocation?.accuracyM, 4.7);
    });

    test('skips an unusable EXIF accuracy for a usable platform one', () {
      final location = photoLocation(
        iphonePhoto(gpsHPositioningErrorM: 0, platformAccuracyM: 8),
      );
      expect(location.reportLocation?.accuracyM, 8);
    });
  });

  group('Exact point, accuracy unknown: never invented', () {
    test('when neither EXIF nor the platform states one', () {
      final location = photoLocation(iphonePhoto(gpsHPositioningErrorM: null));
      expect(location, isA<AccuracyUnknownLocation>());
      final unknown = location as AccuracyUnknownLocation;
      expect(unknown.latitude, -41.2706319);
      expect(unknown.longitude, 173.2839653);
      expect(location.reportLocation, isNull);
    });

    test('ignores GPSDOP, which is not a distance', () {
      final location = photoLocation(
        iphonePhoto(gpsHPositioningErrorM: null, gpsDop: 1.2),
      );
      expect(location, isA<AccuracyUnknownLocation>());
    });

    test('when the accuracy is zero, negative or not finite', () {
      // iOS marks an invalid CLLocation accuracy with a negative number.
      for (final bad in [0.0, -1.0, double.nan, double.infinity]) {
        final location = photoLocation(
          iphonePhoto(gpsHPositioningErrorM: bad, platformAccuracyM: bad),
        );
        expect(location, isA<AccuracyUnknownLocation>(), reason: '$bad');
      }
    });

    test('when the accuracy is beyond what the schema can carry', () {
      final location = photoLocation(
        iphonePhoto(gpsHPositioningErrorM: maxAccuracyM + 1),
      );
      expect(location, isA<AccuracyUnknownLocation>());
    });

    test('but keeps an accuracy exactly at the schema limit', () {
      final location = photoLocation(
        iphonePhoto(gpsHPositioningErrorM: maxAccuracyM),
      );
      expect(location.reportLocation?.accuracyM, maxAccuracyM);
    });
  });

  group('Redacted by the OS', () {
    test('when location access is denied, whatever the tags say', () {
      // Android 10+ without ACCESS_MEDIA_LOCATION: the tags may read (0, 0)
      // or even look plausible, and none of them can be trusted.
      for (final raw in [
        iphonePhoto(locationAccess: LocationAccess.denied),
        iphonePhoto(
          locationAccess: LocationAccess.denied,
          latitude: 0,
          longitude: 0,
        ),
        iphonePhoto(
          locationAccess: LocationAccess.denied,
          latitude: null,
          longitude: null,
        ),
      ]) {
        final location = photoLocation(raw);
        expect(location, isA<RedactedLocation>());
        expect(location.reportLocation, isNull);
      }
    });
  });

  group('Missing', () {
    test('when there are no GPS tags', () {
      final location = photoLocation(
        iphonePhoto(latitude: null, longitude: null),
      );
      expect(location, isA<MissingLocation>());
      expect(location.reportLocation, isNull);
    });

    test('when only one coordinate is present', () {
      expect(
        photoLocation(iphonePhoto(longitude: null)),
        isA<MissingLocation>(),
      );
    });

    test('at (0, 0), the fallback for unreadable GPS, not a place', () {
      expect(
        photoLocation(iphonePhoto(latitude: 0, longitude: 0)),
        isA<MissingLocation>(),
      );
    });

    test('when a coordinate is out of range or not finite', () {
      for (final raw in [
        iphonePhoto(latitude: 91),
        iphonePhoto(longitude: -180.5),
        iphonePhoto(latitude: double.nan),
      ]) {
        expect(photoLocation(raw), isA<MissingLocation>());
      }
    });
  });
}
