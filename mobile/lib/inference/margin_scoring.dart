import 'dart:math' as math;
import 'dart:typed_data';

class TargetMargin {
  const new({
    required this.taxon,
    required this.similarity,
    required this.margin,
    required this.windowIndex,
  });
  final String taxon;
  final double similarity;
  final double margin;
  final int windowIndex;
}

/// Raw ranking evidence without a declared device score meaning.
class MarginSummary {
  new _(this.targets, this.best);
  final List<TargetMargin> targets;
  final TargetMargin best;
}

/// L2-normalize one tower output, then dot it with verified unit text rows.
List<double> cosineSimilarities(
  List<double> embedding,
  List<List<double>> textRows,
) {
  if (embedding.isEmpty ||
      embedding.any((v) => !v.isFinite) ||
      textRows.isEmpty) {
    throw ArgumentError('Finite nonempty embeddings are required');
  }
  // Scale first, so large finite native outputs cannot overflow the norm.
  final scale = embedding.fold<double>(0, (m, v) => math.max(m, v.abs()));
  if (scale == 0) throw ArgumentError('A zero embedding has no direction');
  final scaled = embedding.map((v) => v / scale).toList();
  final norm = math.sqrt(scaled.fold<double>(0, (sum, v) => sum + v * v));
  return textRows
      .map((row) {
        if (row.length != embedding.length || row.any((v) => !v.isFinite)) {
          throw ArgumentError(
            'Text rows and embeddings must have matching dimensions',
          );
        }
        var dot = 0.0;
        for (var i = 0; i < row.length; i++) {
          dot += scaled[i] / norm * row[i];
        }
        return dot;
      })
      .toList(growable: false);
}

/// Ranking 4: best target-minus-comparison margin over eligible windows.
/// Whole-frame index 0 is always eligible, and the first window/target wins ties.
MarginSummary summarizeMargins({
  required List<List<double>> similarities,
  required List<String> targetTaxa,
  required List<bool> eligible,
}) {
  final count = targetTaxa.length;
  if (count == 0 ||
      targetTaxa.toSet().length != count ||
      similarities.isEmpty ||
      eligible.length != similarities.length ||
      !eligible.first) {
    throw ArgumentError(
      'Targets and an eligible whole-frame window are required',
    );
  }
  final columns = similarities.first.length;
  if (columns <= count ||
      similarities.any(
        (row) => row.length != columns || row.any((v) => !v.isFinite),
      )) {
    throw ArgumentError(
      'Every window needs finite target and comparison scores',
    );
  }
  final comparisons = similarities
      .map((row) => row.skip(count).reduce(math.max))
      .toList();
  final targets = <TargetMargin>[];
  for (var target = 0; target < count; target++) {
    var winner = 0;
    var margin = similarities[0][target] - comparisons[0];
    for (var window = 1; window < similarities.length; window++) {
      final next = similarities[window][target] - comparisons[window];
      if (eligible[window] && next > margin) {
        winner = window;
        margin = next;
      }
    }
    targets.add(
      TargetMargin(
        taxon: targetTaxa[target],
        similarity: _sixPlaces(similarities[winner][target]),
        margin: _sixPlaces(margin),
        windowIndex: winner,
      ),
    );
  }
  var best = targets.first;
  for (final target in targets.skip(1)) {
    if (target.margin > best.margin) best = target;
  }
  return MarginSummary._(List.unmodifiable(targets), best);
}

// Match Python round(value, 6), including exact binary half ties. Rounding the
// product value*1e6 can round again before the tie check.
double _sixPlaces(double value) {
  if (!value.isFinite) throw ArgumentError('Nonfinite margin');
  final data = ByteData(8)..setFloat64(0, value);
  final high = data.getUint32(0);
  final low = data.getUint32(4);
  final exponent = (high >> 20) & 0x7ff;
  final fraction = (BigInt.from(high & 0xfffff) << 32) | BigInt.from(low);
  final mantissa = exponent == 0 ? fraction : fraction | (BigInt.one << 52);
  final shift = (exponent == 0 ? 1 : exponent) - 1023 - 52;
  var numerator = mantissa * BigInt.from(1000000);
  final denominator = shift < 0 ? BigInt.one << -shift : BigInt.one;
  if (shift >= 0) numerator <<= shift;
  var rounded = numerator ~/ denominator;
  final twiceRemainder = (numerator % denominator) * BigInt.two;
  if (twiceRemainder > denominator ||
      (twiceRemainder == denominator && rounded.isOdd)) {
    rounded += BigInt.one;
  }
  final result = rounded.toDouble() / 1000000;
  return high >> 31 == 1 ? -result : result;
}
