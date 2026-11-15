/// The photo library as the scan sees it, behind an interface so the scan
/// logic runs and is tested without a phone (#53).
library;

import 'dart:typed_data';

import 'package:meta/meta.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_index.dart';

/// One photo in the library: only what the scan needs to decide about it.
@immutable
final class LibraryAsset {
  const new({
    required this.id,
    required this.createdAt,
    required this.modifiedAt,
    required this.width,
    required this.height,
  });

  /// The platform's id (`PHAsset.localIdentifier`, or the MediaStore id).
  final String id;
  final DateTime createdAt;

  /// Changes when the photo is edited, so an edited photo is screened again.
  final DateTime modifiedAt;
  final int width;
  final int height;

  ScanCursor get cursor => ScanCursor(createdAt: createdAt, id: id);
}

/// A position in newest-first order: capture time, then id to break ties.
///
/// A keyset rather than an offset, so photos taken while a scan is under way
/// do not shift where it resumes.
@immutable
final class ScanCursor {
  const new({required this.createdAt, required this.id});

  final DateTime createdAt;
  final String id;

  /// Whether [asset] comes after this position in newest-first order.
  bool precedes(LibraryAsset asset) => _compare(createdAt, id, asset) < 0;

  @override
  bool operator ==(Object other) =>
      other is ScanCursor &&
      other.createdAt.isAtSameMomentAs(createdAt) &&
      other.id == id;

  @override
  int get hashCode => Object.hash(createdAt.microsecondsSinceEpoch, id);

  @override
  String toString() => 'ScanCursor($createdAt, $id)';
}

int _compare(DateTime createdAt, String id, LibraryAsset b) {
  final byTime = b.createdAt.compareTo(createdAt);
  return byTime != 0 ? byTime : b.id.compareTo(id);
}

/// Sorts newest first, breaking ties by id (descending).
int newestFirst(LibraryAsset a, LibraryAsset b) =>
    _compare(a.createdAt, a.id, b);

/// The image a screener looks at: encoded bytes (JPEG), already scaled
/// down on the phone. It never leaves the phone.
@immutable
final class ScanImage {
  const new(this.bytes);

  final Uint8List bytes;
}

/// What loading a photo for screening gave.
sealed class LoadOutcome {
  const new();
}

final class ImageLoaded extends LoadOutcome {
  const new(this.image);

  final ScanImage image;
}

/// The photo cannot be screened, for example because it is only in iCloud.
final class ImageSkipped extends LoadOutcome {
  const new(this.reason);

  final SkipReason reason;
}

abstract interface class PhotoLibrary {
  /// The access the person has granted, without asking.
  Future<PhotoAccess> access();

  /// Asks the person for access, if the platform still allows asking.
  Future<PhotoAccess> requestAccess();

  /// Opens the system picker so the person can change a limited selection.
  Future<void> changeSelection();

  /// How many photos the app can see.
  Future<int> count();

  /// Up to about [limit] photos after [cursor] in newest-first order (from
  /// the newest when [cursor] is null). An empty list means the end.
  Future<List<LibraryAsset>> olderThan(
    ScanCursor? cursor, {
    required int limit,
  });

  /// Loads [asset] for screening. Never downloads from the cloud.
  Future<LoadOutcome> load(LibraryAsset asset);
}

/// Photos captured from [oldest] to [newest] inclusive (either bound may be
/// absent), newest capture first, at most [limit] when given. Photo
/// libraries order by capture time only, so ties come back in any order.
typedef CaptureRangeQuery = Future<List<LibraryAsset>> Function({
  DateTime? newest,
  DateTime? oldest,
  int? limit,
});

/// The next page after [cursor], built from capture-time range queries.
///
/// The plugin reports capture times in whole seconds, so bursts share them,
/// while the platform may filter on the exact time, to below a millisecond.
/// So every query is inclusive at whole seconds and its results are filtered
/// on the reported time, and a page always holds every photo reported in the
/// same second as its last one, sorted by id. The cursor then never falls in
/// the middle of an unsorted tie. A page may be a little longer than [limit].
Future<List<LibraryAsset>> pageOlderThan(
  ScanCursor? cursor, {
  required int limit,
  required CaptureRangeQuery query,
}) async {
  // Every photo reported as captured in [second]. Its true time lies in
  // [second, second + 1s), inside the inclusive range asked for.
  Future<List<LibraryAsset>> sameSecond(DateTime second) async => [
    for (final a in await query(
      oldest: second,
      newest: second.add(const Duration(seconds: 1)),
    ))
      if (a.createdAt.isAtSameMomentAs(second)) a,
  ];

  final page = <LibraryAsset>[];
  var older = <LibraryAsset>[];
  if (cursor == null) {
    older = await query(limit: limit);
  } else {
    final c = cursor.createdAt;
    final ties = await sameSecond(c);
    page.addAll(ties.where(cursor.precedes));
    // Up to `c` inclusive, so a true time just short of `c` is not lost. Any
    // photo reported at `c` that comes back is one of `ties`, so asking for
    // that many more still leaves [limit] older ones.
    older = [
      for (final a in await query(newest: c, limit: limit + ties.length))
        if (a.createdAt.isBefore(c)) a,
    ];
  }
  if (older.isNotEmpty) {
    final ties = await sameSecond(older.last.createdAt);
    final ids = {for (final a in ties) a.id};
    page
      ..addAll(older.where((a) => !ids.contains(a.id)))
      ..addAll(ties);
  }
  return page..sort(newestFirst);
}
