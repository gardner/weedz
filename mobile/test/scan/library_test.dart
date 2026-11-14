import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/scan/library.dart';

import 'fakes.dart';

/// A platform query that orders by capture time only, like PhotoKit and
/// MediaStore: photos taken in the same second come back in any order (here,
/// insertion order), not by id.
CaptureRangeQuery platformQuery(List<LibraryAsset> assets) =>
    ({newest, oldest, limit}) async {
      final sorted =
          assets
              .where((a) => newest == null || !a.createdAt.isAfter(newest))
              .where((a) => oldest == null || !a.createdAt.isBefore(oldest))
              .toList()
            ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return limit == null ? sorted : sorted.take(limit).toList();
    };

Future<List<String>> walk(List<LibraryAsset> assets, {int limit = 2}) async {
  final seen = <String>[];
  ScanCursor? cursor;
  while (true) {
    final page = await pageOlderThan(
      cursor,
      limit: limit,
      query: platformQuery(assets),
    );
    if (page.isEmpty) return seen;
    seen.addAll(page.map((a) => a.id));
    cursor = page.last.cursor;
  }
}

void main() {
  group('Newest-first order', () {
    test('puts newer photos first, and breaks ties by id', () {
      final list = [
        asset('a', minutes: 1),
        asset('c', minutes: 2),
        asset('b', minutes: 2),
      ]..sort(newestFirst);
      expect(list.map((a) => a.id), ['c', 'b', 'a']);
    });

    test('a cursor precedes exactly the photos after it in that order', () {
      final cursor = asset('b', minutes: 2).cursor;
      expect(cursor.precedes(asset('a', minutes: 2)), isTrue);
      expect(cursor.precedes(asset('z', minutes: 1)), isTrue);
      expect(cursor.precedes(asset('b', minutes: 2)), isFalse);
      expect(cursor.precedes(asset('c', minutes: 2)), isFalse);
      expect(cursor.precedes(asset('a', minutes: 3)), isFalse);
    });
  });

  group('Paging by cursor', () {
    test(
      'visits every photo once, even when many share a capture time',
      () async {
        final assets = [
          for (final id in ['e', 'a', 'd', 'b', 'c']) asset(id, minutes: 5),
          asset('old', minutes: 1),
          asset('new', minutes: 9),
        ];
        expect(await walk(assets), ['new', 'e', 'd', 'c', 'b', 'a', 'old']);
      },
    );

    test('finds photos whose true capture time is part-way through the second '
        'the plugin reports', () async {
      // PhotoKit filters on the exact creation date, but photo_manager
      // reports it truncated to whole seconds.
      final second = day.add(const Duration(minutes: 5));
      final exact = {
        'a': second.add(const Duration(milliseconds: 250)),
        'b': second.add(const Duration(milliseconds: 750)),
        'c': second.add(const Duration(milliseconds: 500)),
      };
      final assets = [
        for (final id in exact.keys) asset(id, minutes: 5),
        asset('old', minutes: 1),
      ];
      Future<List<LibraryAsset>> query({
        DateTime? newest,
        DateTime? oldest,
        int? limit,
      }) async {
        DateTime when(LibraryAsset a) => exact[a.id] ?? a.createdAt;
        final hits =
            assets
                .where((a) => newest == null || !when(a).isAfter(newest))
                .where((a) => oldest == null || !when(a).isBefore(oldest))
                .toList()
              ..sort((a, b) => when(b).compareTo(when(a)));
        return limit == null ? hits : hits.take(limit).toList();
      }

      final seen = <String>[];
      ScanCursor? cursor;
      while (true) {
        final page = await pageOlderThan(cursor, limit: 1, query: query);
        if (page.isEmpty) break;
        seen.addAll(page.map((a) => a.id));
        cursor = page.last.cursor;
      }
      expect(seen, ['c', 'b', 'a', 'old']);
    });

    test('is not shifted by photos taken after the scan started', () async {
      final assets = [for (var m = 0; m < 6; m++) asset('p$m', minutes: m)];
      final first = await pageOlderThan(
        null,
        limit: 3,
        query: platformQuery(assets),
      );
      expect(first.map((a) => a.id), ['p5', 'p4', 'p3']);

      assets.add(asset('fresh', minutes: 99));
      final second = await pageOlderThan(
        first.last.cursor,
        limit: 3,
        query: platformQuery(assets),
      );
      expect(second.map((a) => a.id), ['p2', 'p1', 'p0']);
    });

    test('ends with an empty page', () async {
      final assets = [asset('only')];
      final page = await pageOlderThan(
        asset('only').cursor,
        limit: 5,
        query: platformQuery(assets),
      );
      expect(page, isEmpty);
    });
  });

  group('A cursor', () {
    test('survives a round trip through storage', () {
      final cursor = asset('x', minutes: 7).cursor;
      final restored = ScanCursor(
        createdAt: DateTime.fromMicrosecondsSinceEpoch(
          cursor.createdAt.microsecondsSinceEpoch,
          isUtc: true,
        ),
        id: cursor.id,
      );
      expect(restored, cursor);
    });
  });
}
