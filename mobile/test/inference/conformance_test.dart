import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:weedz/inference/image_windows.dart';
import 'package:weedz/inference/margin_scoring.dart';
import 'package:weedz/inference/window_geometry.dart';

void main() {
  final envelope = jsonDecode(
    File('test/fixtures/model_bundle/envelope.json').readAsStringSync(),
  ) as Map;
  final manifest = jsonDecode(
    utf8.decode(base64Decode(envelope['payload'] as String)),
  ) as Map;

  test('ranking-4 geometry reproduces all publisher vectors and even ties', () {
    for (final item in (manifest['windows'] as Map)['examples'] as List) {
      final example = item as Map;
      expect(
        regionBoxes(
          example['width'] as int,
          example['height'] as int,
        ).map(boxEdges).toList(),
        example['boxes'],
      );
    }
    expect(
      [roundEven(0.5), roundEven(1.5), roundEven(2.5), roundEven(-1.5)],
      [0, 2, 2, -2],
    );
    expect(regionBoxes(1, 1), [(left: 0, top: 0, right: 1, bottom: 1)]);
  });

  test(
    'margin scoring reproduces reduced publisher vectors and winning ties',
    () {
      final taxa = (manifest['watchlist'] as List)
          .map((v) => (v as Map)['taxon'] as String)
          .toList();
      for (final item in (manifest['scoring'] as Map)['examples'] as List) {
        final example = item as Map;
        final similarities = (example['similarities'] as List)
            .map((r) => (r as List).map((v) => (v as num).toDouble()).toList())
            .toList();
        final excluded = example['featureless_windows'] as List;
        final result = summarizeMargins(
          similarities: similarities,
          targetTaxa: taxa,
          eligible: List.generate(
            similarities.length,
            (i) => !excluded.contains(i),
          ),
        );
        expect(result.best.taxon, example['best_species']);
        expect({
          for (final item in result.targets) item.taxon: item.margin,
        }, example['margins']);
      }
      final tie = summarizeMargins(
        similarities: [
          [1, 1, 0],
          [1, 1, 0],
        ],
        targetTaxa: ['a', 'b'],
        eligible: [true, true],
      );
      expect(tie.best.taxon, 'a');
      expect(tie.best.windowIndex, 0);
    },
  );

  test(
    'embedding cosine scoring normalizes tower output and rejects bad data',
    () {
      expect(
        cosineSimilarities(
          [3, 4],
          [
            [1, 0],
            [0, 1],
          ],
        ),
        [0.6, 0.8],
      );
      for (final bad in <List<double>>[
        [0, 0],
        [double.nan, 1],
        [1],
      ]) {
        expect(
          () => cosineSimilarities(bad, [
            [1, 0],
          ]),
          throwsArgumentError,
        );
      }
      expect(
        () => summarizeMargins(
          similarities: [
            [1, double.nan],
          ],
          targetTaxa: ['a'],
          eligible: [true],
        ),
        throwsArgumentError,
      );
    },
  );

  test('server rounds target results before selecting the best species', () {
    final result = summarizeMargins(
      similarities: [
        [0.10000001, 0.10000002, 0],
      ],
      targetTaxa: ['first', 'second'],
      eligible: [true],
    );
    expect(result.best.taxon, 'first');
    expect(result.best.margin, 0.1);
    final tie = summarizeMargins(
      similarities: [
        [0.0078125, 0],
      ],
      targetTaxa: ['only'],
      eligible: [true],
    );
    expect(tie.best.margin, 0.007812);
  });

  group('Python image goldens', () {
    const folder = 'test/fixtures/model_conformance';
    final expected =
        jsonDecode(File('$folder/expected.json').readAsStringSync()) as Map;
    for (final item in expected['cases'] as List) {
      final fixture = item as Map;
      test(
        '${fixture['source']}: upright pixels, crops and featureless threshold',
        () {
          final upright = decodeUpright(
            File('$folder/${fixture['source']}').readAsBytesSync(),
          );
          expect([upright.width, upright.height], fixture['upright_size']);
          final golden = img.decodePng(
            File('$folder/${fixture['upright']}').readAsBytesSync(),
          )!;
          // JPEG IDCT implementations can differ by a small per-channel amount;
          // PNG threshold fixtures require exact equality.
          final tolerance = (fixture['source'] as String).endsWith('.jpg')
              ? 3
              : 0;
          expectPixels(upright, golden, tolerance);
          final boxes = regionBoxes(upright.width, upright.height);
          final windows = fixture['windows'] as List;
          expect(
            boxes.map(boxEdges).toList(),
            windows.map((v) => (v as Map)['box']).toList(),
          );
          for (var i = 0; i < boxes.length; i++) {
            final window = windows[i] as Map;
            expectPixels(
              squareWindow(upright, boxes[i]),
              img.decodePng(
                File('$folder/${window['square']}').readAsBytesSync(),
              )!,
              tolerance,
            );
            expect(isFeatureless(upright, boxes[i]), window['featureless']);
            expect(
              i == 0 || !isFeatureless(upright, boxes[i]),
              window['eligible'],
            );
          }
        },
      );
    }
  });
}

void expectPixels(img.Image actual, img.Image expected, int tolerance) {
  expect([actual.width, actual.height], [expected.width, expected.height]);
  var maximum = 0;
  for (var y = 0; y < actual.height; y++) {
    for (var x = 0; x < actual.width; x++) {
      final a = actual.getPixel(x, y);
      final b = expected.getPixel(x, y);
      for (final difference in [
        (a.r - b.r).abs(),
        (a.g - b.g).abs(),
        (a.b - b.b).abs(),
      ]) {
        if (difference > maximum) maximum = difference.toInt();
      }
    }
  }
  expect(maximum, lessThanOrEqualTo(tolerance));
}
