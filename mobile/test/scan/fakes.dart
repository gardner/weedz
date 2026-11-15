import 'dart:typed_data';

import 'package:drift/native.dart';
import 'package:weedz/scan/drift_scan_index.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_governor.dart';
import 'package:weedz/scan/screener.dart';

/// A fixed day, so each asset's capture time is easy to read in tests.
final day = DateTime.utc(2026, 11, 14);

/// An asset taken [minutes] after the start of [day]: larger is newer.
LibraryAsset asset(
  String id, {
  int minutes = 0,
  int width = 4032,
  int height = 3024,
  DateTime? modifiedAt,
}) {
  final createdAt = day.add(Duration(minutes: minutes));
  return LibraryAsset(
    id: id,
    createdAt: createdAt,
    modifiedAt: modifiedAt ?? createdAt,
    width: width,
    height: height,
  );
}

/// A photo library in memory. Each asset loads as an image unless [outcomes]
/// says otherwise, for example `ImageSkipped(SkipReason.cloudOnly)`.
final class FakeLibrary implements PhotoLibrary {
  new(
    Iterable<LibraryAsset> assets, {
    this.accessState = PhotoAccess.full,
    Map<String, LoadOutcome>? outcomes,
  }) : assets = assets.toList(),
       outcomes = outcomes ?? {};

  final List<LibraryAsset> assets;
  final Map<String, LoadOutcome> outcomes;
  PhotoAccess accessState;

  /// Ids whose load throws, like a corrupt file.
  final Set<String> broken = {};

  /// Every id that was loaded, in order.
  final List<String> loaded = [];
  int selectionChanges = 0;

  @override
  Future<PhotoAccess> access() async => accessState;

  @override
  Future<PhotoAccess> requestAccess() async => accessState;

  @override
  Future<void> changeSelection() async => selectionChanges++;

  @override
  Future<int> count() async =>
      accessState == PhotoAccess.denied ? 0 : assets.length;

  @override
  Future<List<LibraryAsset>> olderThan(
    ScanCursor? cursor, {
    required int limit,
  }) async {
    if (accessState == PhotoAccess.denied) return const [];
    final sorted = [...assets]..sort(newestFirst);
    return sorted
        .where((a) => cursor == null || cursor.precedes(a))
        .take(limit)
        .toList();
  }

  @override
  Future<LoadOutcome> load(LibraryAsset asset) async {
    loaded.add(asset.id);
    if (broken.contains(asset.id)) throw StateError('corrupt ${asset.id}');
    return outcomes[asset.id] ??
        ImageLoaded(ScanImage(Uint8List.fromList(asset.id.codeUnits)));
  }
}

/// Scores each image by a fixed table, and remembers what it saw.
final class FakeScreener implements Screener {
  new({this.modelRevision = 'bioclip2-fp16-r1'});

  @override
  final String modelRevision;

  /// The asset ids screened, decoded from the fake image bytes.
  final List<String> screened = [];

  /// Called before each screening; a test can pause the scan from here.
  void Function(String id)? onScreen;

  /// Ids the model fails on, like an odd thumbnail or running out of memory.
  final Set<String> failing = {};

  @override
  Future<Margins> screen(ScanImage image) async {
    final id = String.fromCharCodes(image.bytes);
    screened.add(id);
    onScreen?.call(id);
    if (failing.contains(id)) throw StateError('model failed on $id');
    return {'Ulex europaeus': id.length / 100, 'Clematis vitalba': -0.1};
  }
}

/// Allows a fixed number of batches, then says the phone needs a rest.
final class FakeGovernor implements ScanGovernor {
  new({this.allowedBatches = 1 << 30});

  int allowedBatches;
  int asked = 0;

  @override
  Future<bool> mayContinue() async => asked++ < allowedBatches;
}

/// A fresh in-memory SQLite index.
DriftScanIndex memoryIndex() => DriftScanIndex(NativeDatabase.memory());
