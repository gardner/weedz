/// Works through the photo library, newest first, a batch at a time (#53).
///
/// It only reads photos and writes the local index. It has no way to send
/// anything off the phone: only reports the person approves are sent (#56).
library;

import 'dart:async';

import 'package:meta/meta.dart';
import 'package:weedz/scan/coverage.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/scan_governor.dart';
import 'package:weedz/scan/scan_index.dart';
import 'package:weedz/scan/screener.dart';

enum ScanState {
  /// A batch is done and more are coming.
  running,

  /// Stopped on request. Run again to resume.
  paused,

  /// Resting because the phone is hot, the battery is low, or the OS asked.
  deviceBusy,

  /// Every photo the app can see has been screened or skipped.
  finished,

  /// The app cannot see the library.
  noAccess,
}

@immutable
final class ScanProgress {
  const new(this.state, this.coverage);

  final ScanState state;
  final ScanCoverage coverage;
}

final class ScanOrchestrator {
  new({
    required this._library,
    required this._index,
    required this._screener,
    this._governor = const AlwaysContinue(),
    this.batchSize = 50,
    this.minimumSide = 224,
  });

  final PhotoLibrary _library;
  final ScanIndex _index;
  final Screener _screener;
  final ScanGovernor _governor;

  /// Photos listed per batch. Progress is reported after each batch.
  final int batchSize;

  /// Photos whose shorter side is below this (the model's input size, in
  /// pixels) are skipped as too small.
  final int minimumSide;

  bool _running = false;
  bool _stopRequested = false;

  bool get isRunning => _running;

  /// Stops after the photo in hand. Run again to resume.
  void pause() => _stopRequested = true;

  /// Scans from where the index left off, reporting progress after each
  /// batch. The stream ends when the scan finishes, pauses or rests.
  /// Cancelling the subscription pauses the scan too.
  Stream<ScanProgress> run() {
    if (_running) throw StateError('A scan is already running');
    _running = true;
    _stopRequested = false;
    final controller = StreamController<ScanProgress>();
    controller
      ..onListen = () {
        unawaited(
          _scan(controller.add)
              .then(controller.add, onError: controller.addError)
              .whenComplete(() {
                _running = false;
                return controller.close();
              }),
        );
      }
      ..onCancel = pause;
    return controller.stream;
  }

  Future<ScanProgress> _scan(void Function(ScanProgress) report) async {
    if (!(await _library.access()).canScan) {
      return await _progress(ScanState.noAccess);
    }
    while (true) {
      if (_stopRequested) return await _progress(ScanState.paused);
      if (!await _governor.mayContinue()) {
        return await _progress(ScanState.deviceBusy);
      }
      // Give way to the UI and other work between batches.
      await Future<void>.delayed(Duration.zero);
      if (_stopRequested) return await _progress(ScanState.paused);

      final position = await _index.position();
      final batch = await _library.olderThan(position.cursor, limit: batchSize);
      if (batch.isEmpty) {
        await _index.finishPass();
        return await _progress(ScanState.finished);
      }
      await _scanBatch(batch, position);
      report(await _progress(ScanState.running));
    }
  }

  /// Records the batch as seen, then decides each photo in turn, moving the
  /// cursor with each decision so a restart resumes after the last one.
  Future<void> _scanBatch(List<LibraryAsset> batch, ScanPosition at) async {
    final revision = _screener.modelRevision;
    final known = await _index.recordsFor(batch.map((a) => a.id));
    final todo = <LibraryAsset>[];
    final listed = <AssetRecord>[];
    for (final asset in batch) {
      final record = known[asset.id];
      if (record != null && record.isCurrent(asset, revision)) {
        listed.add(record.seenIn(at.pass));
      } else {
        todo.add(asset);
        listed.add(
          SeenAsset(
            id: asset.id,
            modifiedAt: asset.modifiedAt,
            seenInPass: at.pass,
          ),
        );
      }
    }
    // The cursor sits just before the next photo still to do, so it skips
    // past photos whose records still hold.
    ScanCursor? cursorBefore(LibraryAsset? next) {
      if (next == null) return batch.last.cursor;
      final i = batch.indexOf(next);
      return i == 0 ? at.cursor : batch[i - 1].cursor;
    }

    await _index.save(listed, cursor: cursorBefore(todo.firstOrNull));
    for (var i = 0; i < todo.length; i++) {
      if (_stopRequested) return;
      final record = await _decide(todo[i], at.pass);
      await _index.save([
        record,
      ], cursor: cursorBefore(todo.elementAtOrNull(i + 1)));
    }
  }

  Future<AssetRecord> _decide(LibraryAsset asset, int pass) async {
    AssetRecord skip(SkipReason reason) => SkippedAsset(
      id: asset.id,
      modifiedAt: asset.modifiedAt,
      seenInPass: pass,
      reason: reason,
    );

    if (asset.width < minimumSide || asset.height < minimumSide) {
      return skip(SkipReason.tooSmall);
    }
    // A photo that fails to load or to screen is skipped as unreadable, and
    // tried again next pass, rather than stopping the scan at it for good.
    try {
      return switch (await _library.load(asset)) {
        ImageSkipped(:final reason) => skip(reason),
        ImageLoaded(:final image) => ScreenedAsset(
          id: asset.id,
          modifiedAt: asset.modifiedAt,
          seenInPass: pass,
          modelRevision: _screener.modelRevision,
          margins: await _screener.screen(image),
        ),
      };
    } on Object {
      return skip(SkipReason.unreadable);
    }
  }

  Future<ScanProgress> _progress(ScanState state) async {
    final access = await _library.access();
    final summary = await _index.summary(_screener.modelRevision);
    return ScanProgress(
      state,
      ScanCoverage(
        access: access,
        total: access.canScan ? await _library.count() : 0,
        screened: summary.screened,
        skipped: summary.skipped,
      ),
    );
  }
}
