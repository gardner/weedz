import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/scan/drift_scan_index.dart';
import 'package:weedz/scan/scan_index.dart';

import 'fakes.dart';

const rev1 = 'bioclip2-fp16-r1';
const rev2 = 'bioclip2-fp16-r2';

ScreenedAsset screened(String id, {int pass = 0, String revision = rev1}) =>
    ScreenedAsset(
      id: id,
      modifiedAt: asset(id).modifiedAt,
      seenInPass: pass,
      modelRevision: revision,
      margins: const {'Ulex europaeus': 0.12, 'Clematis vitalba': -0.03},
    );

SkippedAsset skipped(String id, SkipReason reason, {int pass = 0}) =>
    SkippedAsset(
      id: id,
      modifiedAt: asset(id).modifiedAt,
      seenInPass: pass,
      reason: reason,
    );

void main() {
  group('Whether a record still holds', () {
    final photo = asset('p');

    test('a screening holds for the same photo and model revision', () {
      expect(screened('p').isCurrent(photo, rev1), isTrue);
    });

    test('a new model revision screens the photo again', () {
      expect(screened('p').isCurrent(photo, rev2), isFalse);
    });

    test('an edited photo is screened again', () {
      final edited = asset('p', modifiedAt: day.add(const Duration(days: 1)));
      expect(screened('p').isCurrent(edited, rev1), isFalse);
      expect(
        skipped('p', SkipReason.tooSmall).isCurrent(edited, rev1),
        isFalse,
      );
    });

    test('a photo that is too small or unsupported stays skipped', () {
      for (final reason in [SkipReason.tooSmall, SkipReason.unsupported]) {
        expect(reason.isPermanent, isTrue);
        expect(skipped('p', reason).isCurrent(photo, rev2), isTrue);
      }
    });

    test('a cloud-only or unreadable photo is tried again next pass', () {
      for (final reason in [SkipReason.cloudOnly, SkipReason.unreadable]) {
        expect(reason.isPermanent, isFalse);
        expect(skipped('p', reason).isCurrent(photo, rev1), isFalse);
      }
    });

    test('a photo only seen, not yet decided, still needs screening', () {
      final seen = SeenAsset(id: 'p', modifiedAt: photo.modifiedAt);
      expect(seen.isCurrent(photo, rev1), isFalse);
    });

    test('moving a record to a later pass keeps everything else', () {
      final moved = screened('p').seenIn(4);
      expect(moved.seenInPass, 4);
      expect(moved.margins, screened('p').margins);
      expect(moved.modelRevision, rev1);
    });
  });

  group('The scan index', () {
    late DriftScanIndex index;
    setUp(() => index = memoryIndex());
    tearDown(() => index.close());

    test('starts at the first pass, with no cursor', () async {
      final position = await index.position();
      expect(position.pass, 0);
      expect(position.cursor, isNull);
      final summary = await index.summary(rev1);
      expect(summary.screened, 0);
      expect(summary.skipped, isEmpty);
      expect(summary.waiting, 0);
    });

    test(
      'saves records and the cursor together, and reads them back',
      () async {
        final cursor = asset('b', minutes: 3).cursor;
        await index.save([
          screened('a'),
          skipped('b', SkipReason.cloudOnly),
          SeenAsset(id: 'c', modifiedAt: day),
        ], cursor: cursor);

        expect((await index.position()).cursor, cursor);
        final records = await index.recordsFor(['a', 'b', 'c', 'unknown']);
        expect(records.keys, unorderedEquals(['a', 'b', 'c']));
        final a = records['a']! as ScreenedAsset;
        expect(a.margins, screened('a').margins);
        expect(a.modelRevision, rev1);
        expect(a.modifiedAt, asset('a').modifiedAt);
        expect((records['b']! as SkippedAsset).reason, SkipReason.cloudOnly);
        expect(records['c'], isA<SeenAsset>());
      },
    );

    test('replaces a record with the same id', () async {
      await index.save([SeenAsset(id: 'a', modifiedAt: day)], cursor: null);
      await index.save([screened('a')], cursor: null);
      final records = await index.recordsFor(['a']);
      expect(records['a'], isA<ScreenedAsset>());
    });

    test('counts screenings under the given model, skips by reason, and '
        'photos still waiting', () async {
      await index.save([
        screened('a'),
        screened('b'),
        screened('old', revision: 'bioclip2-fp16-r0'),
        skipped('c', SkipReason.cloudOnly),
        skipped('d', SkipReason.cloudOnly),
        skipped('e', SkipReason.tooSmall),
        SeenAsset(id: 'f', modifiedAt: day),
      ], cursor: null);
      final summary = await index.summary(rev1);
      expect(summary.screened, 2);
      expect(summary.skipped, {
        SkipReason.cloudOnly: 2,
        SkipReason.tooSmall: 1,
      });
      expect(summary.waiting, 1);
    });

    test('finishing a pass forgets photos it did not see, and starts the next '
        'pass from the top', () async {
      await index.save([screened('gone')], cursor: null);
      await index.finishPass();
      await index.save([
        screened('kept', pass: 1),
      ], cursor: asset('kept').cursor);
      await index.finishPass();

      final position = await index.position();
      expect(position.pass, 2);
      expect(position.cursor, isNull);
      expect((await index.recordsFor(['gone', 'kept'])).keys, ['kept']);
    });
  });

  group('After a restart, the scan index', () {
    test('resumes from the same pass, cursor and records', () async {
      final dir = Directory.systemTemp.createTempSync('weedz_scan_');
      addTearDown(() => dir.deleteSync(recursive: true));
      final file = File('${dir.path}/scan.sqlite');
      final cursor = asset('b', minutes: 3).cursor;

      final before = DriftScanIndex(NativeDatabase(file));
      await before.finishPass();
      await before.save([screened('b', pass: 1)], cursor: cursor);
      await before.close();

      final after = DriftScanIndex(NativeDatabase(file));
      addTearDown(after.close);
      final position = await after.position();
      expect(position.pass, 1);
      expect(position.cursor, cursor);
      expect((await after.recordsFor(['b']))['b'], isA<ScreenedAsset>());
    });
  });
}
