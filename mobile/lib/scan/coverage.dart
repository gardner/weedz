/// How much of the library a scan has covered, in numbers and in words, so
/// a partial scan is never mistaken for a whole one (#53).
library;

import 'package:meta/meta.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_index.dart';

@immutable
final class ScanCoverage {
  new({
    required this.access,
    required this.total,
    required this.screened,
    required Map<SkipReason, int> skipped,
  }) : skipped = Map.unmodifiable(skipped);

  final PhotoAccess access;

  /// The photos the app can see: the whole library, or the chosen ones.
  final int total;
  final int screened;
  final Map<SkipReason, int> skipped;

  int get skippedTotal => skipped.values.fold(0, (sum, n) => sum + n);

  int get remaining => (total - screened - skippedTotal).clamp(0, total);

  bool get isComplete => remaining == 0;

  /// For example: "Scanned 1,204 of 5,000 photos. 37 skipped: 30 are stored
  /// only in the cloud, 7 are too small to check."
  String describe() {
    if (!access.canScan) return access.coverageNote!;
    final unit = total == 1 ? 'photo' : 'photos';
    return [
      'Scanned ${_count(screened)} of ${_count(total)} $unit.',
      if (skippedTotal > 0) _skips(),
      ?access.coverageNote,
    ].join(' ');
  }

  String _skips() {
    final reasons = skipped.entries.where((e) => e.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final parts = [
      for (final MapEntry(key: reason, value: n) in reasons)
        '${_count(n)} ${n == 1 ? reason.explanationOne : reason.explanation}',
    ];
    return '${_count(skippedTotal)} skipped: ${parts.join(', ')}.';
  }
}

/// 1204 as "1,204".
String _count(int n) =>
    n.toString().replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');
