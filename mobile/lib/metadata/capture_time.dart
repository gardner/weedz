/// When a photo was taken, and whether its time zone is known (#54).
///
/// EXIF `DateTimeOriginal` is wall-clock time with no zone. Only with
/// `OffsetTimeOriginal` is it an instant, and only an instant goes into a
/// report (the server requires an aware time). No zone is assumed: not the
/// phone's, and not one derived from the GPS time.
library;

import 'package:meta/meta.dart';

/// How far the GPS fix time may be from the capture time and still agree.
const gpsTimeTolerance = Duration(minutes: 2);

@immutable
sealed class CaptureTime {
  const new();

  /// The capture time a report may carry, or null when it may carry none.
  DateTime? get reportCapturedAt => null;
}

/// An exact instant: the camera wrote its offset from UTC.
final class OffsetKnownTime extends CaptureTime {
  const new({required this.instant, required this.offset});

  /// In UTC.
  final DateTime instant;
  final Duration offset;

  @override
  DateTime get reportCapturedAt => instant;

  @override
  bool operator ==(Object other) =>
      other is OffsetKnownTime &&
      other.instant == instant &&
      other.offset == offset;

  @override
  int get hashCode => Object.hash(instant, offset);
}

/// A wall-clock time in an unknown zone: shown, but not sent.
final class LocalOnlyTime extends CaptureTime {
  const new(this.wallClock);

  /// The camera's wall-clock fields, held in a UTC [DateTime] only so that
  /// no zone is applied to them. It is not an instant.
  final DateTime wallClock;

  @override
  bool operator ==(Object other) =>
      other is LocalOnlyTime && other.wallClock == wallClock;

  @override
  int get hashCode => wallClock.hashCode;
}

/// No usable capture time.
final class MissingTime extends CaptureTime {
  const new();

  @override
  bool operator ==(Object other) => other is MissingTime;

  @override
  int get hashCode => (MissingTime).hashCode;
}

/// Whether the GPS fix was taken when the photo was.
@immutable
sealed class GpsTimeCheck {
  const new();
}

final class GpsTimeAgrees extends GpsTimeCheck {
  const new();
}

/// The fix is stale, or the camera clock is wrong: the person is told.
final class GpsTimeDisagrees extends GpsTimeCheck {
  const new(this.by);

  /// How far apart the two times are.
  final Duration by;
}

/// There is no GPS time, or no exact capture time to compare it with.
final class GpsTimeUnavailable extends GpsTimeCheck {
  const new();
}

final _dateTime = RegExp(r'^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$');
final _offset = RegExp(r'^([+-])(\d{2}):(\d{2})$');
final _gpsDate = RegExp(r'^(\d{4}):(\d{2}):(\d{2})$');
final _gpsTime = RegExp(r'^(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$');

/// EXIF strings are fixed-width ASCII, often padded with NULs or spaces.
RegExpMatch? _match(RegExp pattern, String? value) =>
    pattern.firstMatch(value?.replaceAll('\u0000', '').trim() ?? '');

List<int> _ints(RegExpMatch match, int count) => [
  for (var i = 1; i <= count; i++) int.parse(match.group(i)!),
];

/// The fields as UTC, or null when they are not a real calendar time.
DateTime? _utc(List<int> fields, [int millisecond = 0]) {
  final [year, month, day, hour, minute, second] = fields;
  final time = DateTime.utc(
    year,
    month,
    day,
    hour,
    minute,
    second,
    millisecond,
  );
  final real =
      year > 0 &&
      time.year == year &&
      time.month == month &&
      time.day == day &&
      time.hour == hour &&
      time.minute == minute &&
      time.second == second;
  return real ? time : null;
}

/// Wall-clock fields from a `YYYY:MM:DD HH:MM:SS` string.
DateTime? exifWallClock(String? value) {
  final match = _match(_dateTime, value);
  return match == null ? null : _utc(_ints(match, 6));
}

Duration? _parseOffset(String? value) {
  final match = _match(_offset, value);
  if (match == null) return null;
  final hours = int.parse(match.group(2)!);
  final minutes = int.parse(match.group(3)!);
  final size = Duration(hours: hours, minutes: minutes);
  // Real zones lie within UTC-12:00 and UTC+14:00; allow 14 hours either way.
  if (minutes > 59 || size > const Duration(hours: 14)) return null;
  return match.group(1) == '-' ? -size : size;
}

CaptureTime captureTime(String? dateTimeOriginal, String? offsetTimeOriginal) {
  final wallClock = exifWallClock(dateTimeOriginal);
  if (wallClock == null) return const MissingTime();
  final offset = _parseOffset(offsetTimeOriginal);
  if (offset == null) return LocalOnlyTime(wallClock);
  return OffsetKnownTime(instant: wallClock.subtract(offset), offset: offset);
}

/// The GPS fix time, in UTC.
DateTime? gpsTime(String? gpsDateStamp, String? gpsTimeStamp) {
  final date = _match(_gpsDate, gpsDateStamp);
  final time = _match(_gpsTime, gpsTimeStamp);
  if (date == null || time == null) return null;
  final fraction = (time.group(4) ?? '').padRight(3, '0').substring(0, 3);
  return _utc([..._ints(date, 3), ..._ints(time, 3)], int.parse(fraction));
}

GpsTimeCheck checkGpsTime(CaptureTime capture, DateTime? fix) {
  if (capture is! OffsetKnownTime || fix == null) {
    return const GpsTimeUnavailable();
  }
  final by = capture.instant.difference(fix).abs();
  return by <= gpsTimeTolerance ? const GpsTimeAgrees() : GpsTimeDisagrees(by);
}
