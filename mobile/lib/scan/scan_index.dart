/// The local record of what the scan has done, so it can resume after a
/// restart and never screens a photo twice under the same model (#53).
///
/// It stays on the phone. Uninstalling the app deletes it.
library;

import 'package:meta/meta.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/screener.dart';

/// Why a photo was not screened. Each one is counted and explained.
enum SkipReason {
  /// The original is only in iCloud (or another cloud). Not downloaded.
  cloudOnly(
    isPermanent: false,
    explanation: 'are stored only in the cloud',
    explanationOne: 'is stored only in the cloud',
  ),

  /// A format the phone cannot decode for screening.
  unsupported(
    isPermanent: true,
    explanation: "are in a format Weedz can't read",
    explanationOne: "is in a format Weedz can't read",
  ),

  /// Smaller than the model's input, so there is too little to see.
  tooSmall(
    isPermanent: true,
    explanation: 'are too small to check',
    explanationOne: 'is too small to check',
  ),

  /// Loading or screening failed, perhaps only this time.
  unreadable(
    isPermanent: false,
    explanation: 'could not be opened',
    explanationOne: 'could not be opened',
  );

  new({
    required this.isPermanent,
    required this.explanation,
    required this.explanationOne,
  });

  /// Holds until the photo changes. Otherwise the photo is tried again on the
  /// next pass, for example once it has been downloaded from the cloud.
  final bool isPermanent;

  /// Completes "N photos ..." in a coverage report.
  final String explanation;

  /// Completes "1 photo ..." in a coverage report.
  final String explanationOne;
}

/// What the index knows about one photo.
@immutable
sealed class AssetRecord {
  const new({
    required this.id,
    required this.modifiedAt,
    required this.seenInPass,
  });

  final String id;

  /// The photo's modification time when this was recorded.
  final DateTime modifiedAt;

  /// The last pass over the library that saw the photo. A completed pass
  /// forgets photos it did not see: deleted, or no longer shared.
  final int seenInPass;

  /// Whether this record still answers for [asset] under [modelRevision], so
  /// the photo need not be screened again.
  bool isCurrent(LibraryAsset asset, String modelRevision) =>
      asset.modifiedAt.isAtSameMomentAs(modifiedAt) && _holdsFor(modelRevision);

  bool _holdsFor(String modelRevision);

  /// The same record, seen again in [pass].
  AssetRecord seenIn(int pass);
}

/// Listed in a pass, not yet screened or skipped.
final class SeenAsset extends AssetRecord {
  const new({
    required super.id,
    required super.modifiedAt,
    super.seenInPass = 0,
  });

  @override
  bool _holdsFor(String modelRevision) => false;

  @override
  SeenAsset seenIn(int pass) =>
      SeenAsset(id: id, modifiedAt: modifiedAt, seenInPass: pass);
}

/// Screened by [modelRevision], with the best margin per weed.
final class ScreenedAsset extends AssetRecord {
  const new({
    required super.id,
    required super.modifiedAt,
    required super.seenInPass,
    required this.modelRevision,
    required this.margins,
  });

  final String modelRevision;
  final Margins margins;

  @override
  bool _holdsFor(String modelRevision) => modelRevision == this.modelRevision;

  @override
  ScreenedAsset seenIn(int pass) => ScreenedAsset(
    id: id,
    modifiedAt: modifiedAt,
    seenInPass: pass,
    modelRevision: modelRevision,
    margins: margins,
  );
}

/// Not screened, for [reason].
final class SkippedAsset extends AssetRecord {
  const new({
    required super.id,
    required super.modifiedAt,
    required super.seenInPass,
    required this.reason,
  });

  final SkipReason reason;

  @override
  bool _holdsFor(String modelRevision) => reason.isPermanent;

  @override
  SkippedAsset seenIn(int pass) => SkippedAsset(
    id: id,
    modifiedAt: modifiedAt,
    seenInPass: pass,
    reason: reason,
  );
}

/// Where the scan is: which pass over the library, and how far through it.
@immutable
final class ScanPosition {
  const new({required this.pass, required this.cursor});

  final int pass;

  /// The last photo decided in this pass, or null at the start of a pass.
  final ScanCursor? cursor;
}

/// Counts for a coverage report.
@immutable
final class IndexSummary {
  const new({
    required this.screened,
    required this.skipped,
    required this.waiting,
  });

  /// Photos screened under the current model revision.
  final int screened;
  final Map<SkipReason, int> skipped;

  /// Photos listed but not yet decided.
  final int waiting;
}

abstract interface class ScanIndex {
  Future<ScanPosition> position();

  /// The records for those of [ids] the index knows.
  Future<Map<String, AssetRecord>> recordsFor(Iterable<String> ids);

  /// Saves [records] (replacing any with the same id) and moves the cursor
  /// to [cursor], in one transaction, so a crash cannot split them.
  Future<void> save(List<AssetRecord> records, {required ScanCursor? cursor});

  /// Ends the current pass: forgets photos it did not see, and starts the
  /// next pass from the newest photo.
  Future<void> finishPass();

  Future<IndexSummary> summary(String modelRevision);
}
