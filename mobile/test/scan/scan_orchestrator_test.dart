import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/scan/drift_scan_index.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_index.dart';
import 'package:weedz/scan/scan_orchestrator.dart';

import 'fakes.dart';

/// Photos p0 (oldest) to p{n-1} (newest).
List<LibraryAsset> photos(int n) => [
  for (var i = 0; i < n; i++) asset('p$i', minutes: i),
];

void main() {
  late DriftScanIndex index;
  late FakeScreener screener;
  setUp(() {
    index = memoryIndex();
    screener = FakeScreener();
  });
  tearDown(() => index.close());

  ScanOrchestrator orchestrator(
    FakeLibrary library, {
    int batchSize = 2,
    FakeGovernor? governor,
    FakeScreener? withScreener,
  }) => ScanOrchestrator(
    library: library,
    index: index,
    screener: withScreener ?? screener,
    governor: governor ?? FakeGovernor(),
    batchSize: batchSize,
  );

  group('A scan', () {
    test('screens every photo once, newest first, in batches', () async {
      final progress = await orchestrator(FakeLibrary(photos(5)))
          .run()
          .toList();

      expect(screener.screened, ['p4', 'p3', 'p2', 'p1', 'p0']);
      expect(progress.map((p) => p.state), [
        ScanState.running,
        ScanState.running,
        ScanState.running,
        ScanState.finished,
      ]);
      expect(progress.map((p) => p.coverage.screened), [2, 4, 5, 5]);
      final done = progress.last.coverage;
      expect(done.total, 5);
      expect(done.isComplete, isTrue);
    });

    test('keeps the best margin per weed in the index', () async {
      await orchestrator(FakeLibrary([asset('pic')])).run().drain<void>();
      final record = (await index.recordsFor(['pic']))['pic']!;
      expect(record, isA<ScreenedAsset>());
      final screened = record as ScreenedAsset;
      expect(screened.modelRevision, screener.modelRevision);
      expect(screened.margins['Ulex europaeus'], closeTo(0.03, 1e-9));
    });

    test('skips and counts photos it cannot screen, with the reason', () async {
      final library = FakeLibrary(
        [
          asset('fine', minutes: 5),
          asset('cloud', minutes: 4),
          asset('tiny', minutes: 3, width: 160, height: 120),
          asset('raw', minutes: 2),
          asset('corrupt', minutes: 1),
        ],
        outcomes: {
          'cloud': const ImageSkipped(SkipReason.cloudOnly),
          'raw': const ImageSkipped(SkipReason.unsupported),
        },
      )..broken.add('corrupt');

      final last = await orchestrator(library).run().last;

      expect(screener.screened, ['fine']);
      expect(library.loaded, isNot(contains('tiny')));
      expect(last.coverage.screened, 1);
      expect(last.coverage.skipped, {
        SkipReason.cloudOnly: 1,
        SkipReason.tooSmall: 1,
        SkipReason.unsupported: 1,
        SkipReason.unreadable: 1,
      });
      expect(last.coverage.isComplete, isTrue);
    });

    test('skips a photo the model fails on, and carries on', () async {
      screener.failing.add('p1');
      final last = await orchestrator(FakeLibrary(photos(3))).run().last;
      expect(last.state, ScanState.finished);
      expect(screener.screened, ['p2', 'p1', 'p0']);
      expect(last.coverage.screened, 2);
      expect(last.coverage.skipped, {SkipReason.unreadable: 1});
    });

    test('scans nothing without photo access, and says why', () async {
      final library = FakeLibrary(photos(3), accessState: PhotoAccess.denied);
      final progress = await orchestrator(library).run().toList();
      expect(progress.single.state, ScanState.noAccess);
      expect(progress.single.coverage.access, PhotoAccess.denied);
      expect(library.loaded, isEmpty);
    });

    test('covers only the chosen photos under limited access', () async {
      final library = FakeLibrary(photos(2), accessState: PhotoAccess.limited);
      final last = await orchestrator(library).run().last;
      expect(last.coverage.access, PhotoAccess.limited);
      expect(last.coverage.describe(), contains('chose to share'));
    });

    test('cannot be started twice at once', () async {
      final scan = orchestrator(FakeLibrary(photos(3)));
      final first = scan.run().drain<void>();
      expect(() => scan.run().drain<void>(), throwsStateError);
      await first;
      expect(scan.isRunning, isFalse);
    });
  });

  group('A scan that stops part-way', () {
    test(
      'pauses after the photo in hand, and resumes where it left off',
      () async {
        final library = FakeLibrary(photos(6));
        final scan = orchestrator(library, batchSize: 4);
        screener.onScreen = (id) {
          if (id == 'p4') scan.pause();
        };

        final paused = await scan.run().last;
        expect(paused.state, ScanState.paused);
        expect(screener.screened, ['p5', 'p4']);
        expect((await index.summary(screener.modelRevision)).waiting, 2);

        screener.onScreen = null;
        final resumed = await scan.run().last;
        expect(resumed.state, ScanState.finished);
        expect(screener.screened, ['p5', 'p4', 'p3', 'p2', 'p1', 'p0']);
      },
    );

    test('resumes after a restart without screening anything twice', () async {
      final library = FakeLibrary(photos(6));
      // The app is killed after the first batch: the listener goes away.
      await orchestrator(library).run().first;
      expect(screener.screened, ['p5', 'p4']);

      final restarted = FakeScreener();
      await orchestrator(library, withScreener: restarted).run().drain<void>();
      expect(restarted.screened, ['p3', 'p2', 'p1', 'p0']);
    });

    test('yields between batches, so the app stays responsive', () async {
      final scan = orchestrator(FakeLibrary(photos(100)), batchSize: 10);
      final states = <ScanState>[];
      await for (final progress in scan.run()) {
        // A timer, not a microtask: it runs only if the scan gives way.
        if (states.isEmpty) Timer.run(scan.pause);
        states.add(progress.state);
      }
      expect(states.last, ScanState.paused);
      expect(screener.screened.length, inInclusiveRange(10, 90));
    });

    test('rests when the phone is hot or the battery is low', () async {
      final library = FakeLibrary(photos(4));
      final governor = FakeGovernor(allowedBatches: 1);
      final rested = await orchestrator(library, governor: governor).run().last;
      expect(rested.state, ScanState.deviceBusy);
      expect(screener.screened, ['p3', 'p2']);

      governor.allowedBatches = 100;
      final finished = await orchestrator(
        library,
        governor: governor,
      ).run().last;
      expect(finished.state, ScanState.finished);
      expect(screener.screened, ['p3', 'p2', 'p1', 'p0']);
    });
  });

  group('Scanning again', () {
    test('does not screen a photo twice under the same model', () async {
      final library = FakeLibrary(photos(3));
      await orchestrator(library).run().drain<void>();
      final again = await orchestrator(library).run().last;
      expect(screener.screened, ['p2', 'p1', 'p0']);
      expect(again.coverage.screened, 3);
    });

    test('screens everything again under a new model revision', () async {
      final library = FakeLibrary(photos(2));
      await orchestrator(library).run().drain<void>();
      final next = FakeScreener(modelRevision: 'bioclip2-fp16-r2');
      await orchestrator(library, withScreener: next).run().drain<void>();
      expect(next.screened, ['p1', 'p0']);
    });

    test('picks up new photos and tries cloud-only photos again', () async {
      final library = FakeLibrary(
        photos(2),
        outcomes: {'p0': const ImageSkipped(SkipReason.cloudOnly)},
      );
      await orchestrator(library).run().drain<void>();
      expect(screener.screened, ['p1']);

      library.assets.add(asset('fresh', minutes: 60));
      library.outcomes.remove('p0'); // Downloaded from the cloud since.
      final last = await orchestrator(library).run().last;
      expect(screener.screened, ['p1', 'fresh', 'p0']);
      expect(last.coverage.skipped, isEmpty);
    });

    test('forgets deleted photos once a pass completes', () async {
      final library = FakeLibrary(photos(3));
      await orchestrator(library).run().drain<void>();
      library.assets.removeWhere((a) => a.id == 'p1');
      final last = await orchestrator(library).run().last;
      expect(last.coverage.total, 2);
      expect(last.coverage.screened, 2);
    });
  });
}
