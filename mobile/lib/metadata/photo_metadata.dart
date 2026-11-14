/// A photo's place and time, each with an explicit quality state, and what
/// of them a report may carry (#54).
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/metadata/capture_time.dart';
import 'package:weedz/metadata/photo_location.dart';
import 'package:weedz/metadata/raw_photo_metadata.dart';

export 'package:weedz/metadata/capture_time.dart';
export 'package:weedz/metadata/photo_location.dart';
export 'package:weedz/metadata/raw_photo_metadata.dart';

/// A later EXIF modify time than this after capture means the file changed.
const editedAfter = Duration(minutes: 1);

/// Facts about the photo the approval screen should mention.
enum PhotoFlag {
  /// Its metadata describes the screenshot, not the scene.
  screenshot,

  /// Edited after capture: its place and time may have been rewritten.
  edited,

  /// The original is only in the cloud, so its EXIF may not be on the phone.
  cloudOnly,
}

@immutable
final class PhotoMetadata {
  /// Keeps a copy of [flags] no one can change, so the screenshot rule below
  /// cannot be undone.
  new({
    required this.location,
    required this.captureTime,
    required this.gpsTimeCheck,
    required Set<PhotoFlag> flags,
  }) : flags = Set.unmodifiable(flags);

  final PhotoLocation location;
  final CaptureTime captureTime;
  final GpsTimeCheck gpsTimeCheck;
  final Set<PhotoFlag> flags;

  bool get _isScreenshot => flags.contains(PhotoFlag.screenshot);

  /// `Report.location`: only an exact location, and never a screenshot's.
  Location? get reportLocation =>
      _isScreenshot ? null : location.reportLocation;

  /// `Report.capturedAt`: only an exact instant, and never a screenshot's.
  DateTime? get reportCapturedAt =>
      _isScreenshot ? null : captureTime.reportCapturedAt;
}

bool _modifiedAfterCapture(RawPhotoMetadata raw) {
  final taken = exifWallClock(raw.dateTimeOriginal);
  final modified = exifWallClock(raw.dateTime);
  return taken != null &&
      modified != null &&
      modified.difference(taken) > editedAfter;
}

PhotoMetadata extractPhotoMetadata(RawPhotoMetadata raw) {
  final time = captureTime(raw.dateTimeOriginal, raw.offsetTimeOriginal);
  return PhotoMetadata(
    location: photoLocation(raw),
    captureTime: time,
    gpsTimeCheck: checkGpsTime(
      time,
      gpsTime(raw.gpsDateStamp, raw.gpsTimeStamp),
    ),
    flags: {
      if (raw.isScreenshot) PhotoFlag.screenshot,
      if (raw.isEdited || _modifiedAfterCapture(raw)) PhotoFlag.edited,
      if (!raw.isLocallyAvailable) PhotoFlag.cloudOnly,
    },
  );
}

/// Reads a photo on the platform and applies the rules above.
final class PhotoMetadataExtractor {
  const new(this._reader);

  final PhotoMetadataReader _reader;

  Future<PhotoMetadata> extract(String assetId) async =>
      extractPhotoMetadata(await _reader.read(assetId));
}
