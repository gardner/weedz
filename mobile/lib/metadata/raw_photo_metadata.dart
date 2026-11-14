/// What a platform can tell about one photo's place and time, before any
/// rule is applied (#54).
///
/// The platform readers (Android `ExifInterface` on the original, iOS
/// `PHAsset` and `CGImageSource`) only copy these fields. Every judgement
/// about them lives in pure Dart, in `photo_metadata.dart`, so it is tested
/// on any machine.
library;

import 'package:meta/meta.dart';

/// Whether the platform let the app see photo locations.
enum LocationAccess {
  granted,

  /// Android 10+ without `ACCESS_MEDIA_LOCATION`: the system redacts the GPS
  /// tags, so whatever they read is not the photo's location.
  denied,
}

@immutable
final class RawPhotoMetadata {
  const new({
    required this.locationAccess,
    this.latitude,
    this.longitude,
    this.gpsHPositioningErrorM,
    this.platformAccuracyM,
    this.gpsDop,
    this.dateTimeOriginal,
    this.offsetTimeOriginal,
    this.dateTime,
    this.gpsDateStamp,
    this.gpsTimeStamp,
    this.isScreenshot = false,
    this.isEdited = false,
    this.isLocallyAvailable = true,
  });

  final LocationAccess locationAccess;

  /// Signed decimal degrees, with the GPS reference (N/S, E/W) applied.
  final double? latitude;
  final double? longitude;

  /// EXIF `GPSHPositioningError` (0x001F), in metres.
  final double? gpsHPositioningErrorM;

  /// The platform's horizontal accuracy in metres, such as iOS
  /// `CLLocation.horizontalAccuracy` (negative when invalid).
  final double? platformAccuracyM;

  /// EXIF `GPSDOP`: a dilution of precision, with no unit. Never an accuracy.
  final double? gpsDop;

  /// EXIF `DateTimeOriginal` (0x9003), local time: `YYYY:MM:DD HH:MM:SS`.
  final String? dateTimeOriginal;

  /// EXIF `OffsetTimeOriginal` (0x9011): `±HH:MM`.
  final String? offsetTimeOriginal;

  /// EXIF `DateTime` (0x0132): when the file was last changed, local time.
  final String? dateTime;

  /// EXIF `GPSDateStamp` (`YYYY:MM:DD`) and `GPSTimeStamp` (`HH:MM:SS[.ss]`):
  /// when the GPS fix was taken, in UTC.
  final String? gpsDateStamp;
  final String? gpsTimeStamp;

  /// iOS `.photoScreenshot`, or Android's screenshots folder.
  final bool isScreenshot;

  /// iOS `PHAsset.hasAdjustments`, or an Android edit the platform reports.
  final bool isEdited;

  /// False for an iCloud-only or cloud-only original.
  final bool isLocallyAvailable;
}

/// Reads one photo's raw metadata on the platform; faked in tests.
abstract interface class PhotoMetadataReader {
  Future<RawPhotoMetadata> read(String assetId);
}
