/// Where a photo was taken, and how far that can be trusted (#54).
///
/// Only an [ExactLocation] goes into a report: the server requires an
/// accuracy with every location, and its search area is that accuracy plus
/// a 100 m allowance. An accuracy is never invented, so a point without one
/// stays an [AccuracyUnknownLocation] and is shown, not sent.
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/metadata/raw_photo_metadata.dart';

@immutable
sealed class PhotoLocation {
  const new();

  /// The location a report may carry, or null when it may carry none.
  Location? get reportLocation => null;
}

/// Exact coordinates, with the accuracy the camera or platform stated.
final class ExactLocation extends PhotoLocation {
  const new(this.location);

  final Location location;

  @override
  Location get reportLocation => location;

  @override
  bool operator ==(Object other) =>
      other is ExactLocation && other.location == location;

  @override
  int get hashCode => location.hashCode;
}

/// Exact coordinates with no usable accuracy: no search area can be stated.
final class AccuracyUnknownLocation extends PhotoLocation {
  const new({required this.latitude, required this.longitude});

  final double latitude;
  final double longitude;

  @override
  bool operator ==(Object other) =>
      other is AccuracyUnknownLocation &&
      other.latitude == latitude &&
      other.longitude == longitude;

  @override
  int get hashCode => Object.hash(latitude, longitude);
}

/// The platform withheld the location, so the photo may or may not have one.
final class RedactedLocation extends PhotoLocation {
  const new();

  @override
  bool operator ==(Object other) => other is RedactedLocation;

  @override
  int get hashCode => (RedactedLocation).hashCode;
}

/// The photo has no usable location.
final class MissingLocation extends PhotoLocation {
  const new();

  @override
  bool operator ==(Object other) => other is MissingLocation;

  @override
  int get hashCode => (MissingLocation).hashCode;
}

bool _within(double value, double limit) =>
    value.isFinite && value.abs() <= limit;

/// An accuracy the report can carry: positive, finite and within the limit.
double? _usable(double? metres) =>
    metres != null && metres.isFinite && metres > 0 && metres <= maxAccuracyM
    ? metres
    : null;

PhotoLocation photoLocation(RawPhotoMetadata raw) {
  if (raw.locationAccess == LocationAccess.denied) {
    return const RedactedLocation();
  }
  final latitude = raw.latitude;
  final longitude = raw.longitude;
  if (latitude == null ||
      longitude == null ||
      !_within(latitude, 90) ||
      !_within(longitude, 180) ||
      // The fallback for unreadable GPS (Android's own sample code uses it).
      (latitude == 0 && longitude == 0)) {
    return const MissingLocation();
  }
  // The camera's own figure first. GPSDOP has no unit and is never used.
  final accuracy =
      _usable(raw.gpsHPositioningErrorM) ?? _usable(raw.platformAccuracyM);
  if (accuracy == null) {
    return AccuracyUnknownLocation(latitude: latitude, longitude: longitude);
  }
  return ExactLocation(
    Location(latitude: latitude, longitude: longitude, accuracyM: accuracy),
  );
}
