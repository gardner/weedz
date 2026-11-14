import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/metadata/photo_metadata.dart';

import '../domain/fixtures.dart';
import 'raw.dart';

/// A reader that answers from a map, as the platform readers will (#53).
final class FakeReader implements PhotoMetadataReader {
  new(this.photos);

  final Map<String, RawPhotoMetadata> photos;

  @override
  Future<RawPhotoMetadata> read(String assetId) async => photos[assetId]!;
}

void main() {
  group('extractPhotoMetadata', () {
    test('an untouched camera photo is exact in place and time', () {
      final metadata = extractPhotoMetadata(iphonePhoto());
      expect(metadata.location, isA<ExactLocation>());
      expect(metadata.captureTime, isA<OffsetKnownTime>());
      expect(metadata.gpsTimeCheck, isA<GpsTimeAgrees>());
      expect(metadata.flags, isEmpty);
    });

    test('flags a stale fix or a wrong clock, without changing either', () {
      final metadata = extractPhotoMetadata(
        iphonePhoto(gpsTimeStamp: '21:00:00'),
      );
      expect(metadata.gpsTimeCheck, isA<GpsTimeDisagrees>());
      expect(metadata.reportLocation, isNotNull);
      expect(metadata.reportCapturedAt, isNotNull);
    });

    test('flags a screenshot, and takes no place or time from it', () {
      // Its metadata describes the screenshot, not the scene.
      final metadata = extractPhotoMetadata(iphonePhoto(isScreenshot: true));
      expect(metadata.flags, {PhotoFlag.screenshot});
      expect(metadata.reportLocation, isNull);
      expect(metadata.reportCapturedAt, isNull);
    });

    test('a screenshot flag cannot be cleared to release place and time', () {
      final flags = {PhotoFlag.screenshot};
      final metadata = PhotoMetadata(
        location: const MissingLocation(),
        captureTime: const MissingTime(),
        gpsTimeCheck: const GpsTimeUnavailable(),
        flags: flags,
      );
      flags.clear();
      expect(metadata.flags, {PhotoFlag.screenshot});
      expect(
        () =>
            extractPhotoMetadata(iphonePhoto(isScreenshot: true)).flags
              ..clear(),
        throwsUnsupportedError,
      );
    });

    test('flags a photo the platform says was edited', () {
      final metadata = extractPhotoMetadata(iphonePhoto(isEdited: true));
      expect(metadata.flags, {PhotoFlag.edited});
      expect(metadata.reportLocation, isNotNull);
    });

    test('flags a photo whose EXIF modify time moved after capture', () {
      final metadata = extractPhotoMetadata(
        iphonePhoto(dateTime: '2026:10:05 09:00:00'),
      );
      expect(metadata.flags, {PhotoFlag.edited});
    });

    test('does not flag a modify time within a minute of capture', () {
      final metadata = extractPhotoMetadata(
        iphonePhoto(dateTime: '2026:10:03 12:16:30'),
      );
      expect(metadata.flags, isEmpty);
    });

    test('flags a cloud-only original', () {
      final metadata = extractPhotoMetadata(
        iphonePhoto(isLocallyAvailable: false),
      );
      expect(metadata.flags, {PhotoFlag.cloudOnly});
    });
  });

  group('PhotoMetadataExtractor', () {
    test('reads through the platform interface', () async {
      final extractor = PhotoMetadataExtractor(
        FakeReader({'asset-1': iphonePhoto()}),
      );
      final metadata = await extractor.extract('asset-1');
      expect(metadata.location, isA<ExactLocation>());
    });
  });

  group('Mapping onto the report (schema v1, #57)', () {
    test('an exact photo fills location and capture time as the fixture', () {
      final metadata = extractPhotoMetadata(iphonePhoto());
      final report = minimalReport().copyWith(
        location: metadata.reportLocation,
        capturedAt: metadata.reportCapturedAt,
        consent: minimalReport().consent.copyWith(location: true),
      );
      final fixture =
          jsonDecode(fixtureJson('report_v1.json')) as Map<String, Object?>;
      final json = report.toJson();
      expect(json['location'], fixture['location']);
      expect(json['captured_at'], fixture['captured_at']);
    });

    test('unknown accuracy and a local-only time leave both fields out', () {
      final metadata = extractPhotoMetadata(
        iphonePhoto(gpsHPositioningErrorM: null, offsetTimeOriginal: null),
      );
      final json = minimalReport()
          .copyWith(
            location: metadata.reportLocation,
            capturedAt: metadata.reportCapturedAt,
          )
          .toJson();
      expect(json.containsKey('location'), isFalse);
      expect(json.containsKey('captured_at'), isFalse);
    });

    test('a redacted or missing location is never sent', () {
      for (final raw in [
        iphonePhoto(locationAccess: LocationAccess.denied),
        iphonePhoto(latitude: null, longitude: null),
      ]) {
        expect(extractPhotoMetadata(raw).reportLocation, isNull);
      }
    });
  });
}
