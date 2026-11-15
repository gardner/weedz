import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import 'harness.dart';

void main() {
  testWidgets('raw score is visible and technical explanation is optional', (
    tester,
  ) async {
    await pumpApproval(tester, foundCase());
    expect(find.text('Model score: 0.051'), findsOneWidget);
    expect(find.textContaining('not a probability'), findsOneWidget);
    expect(find.textContaining('bioclip-2/ranking-4/meaning-1'), findsNothing);
    expect(find.textContaining('No cut-off'), findsNothing);
    await tapText(tester, 'About this score');
    expect(
      find.textContaining('bioclip-2/ranking-4/meaning-1'),
      findsOneWidget,
    );
    expect(find.textContaining('No cut-off'), findsOneWidget);
    expect(
      find.textContaining('Native plants can score as a weed'),
      findsOneWidget,
    );
  });
  testWidgets('expanded model version matches the exact outgoing model stamp', (
    tester,
  ) async {
    final store = await pumpApproval(tester, foundCase());
    final model = foundCase().report.model.toJson();
    final labels = {
      'Model': 'model_key',
      'Model revision': 'revision',
      'Ranking revision': 'ranking_revision',
    };
    for (final label in labels.entries) {
      expect(find.text('${label.key}: ${model[label.value]}'), findsNothing);
    }
    await tapText(tester, 'About this score');
    for (final label in labels.entries) {
      expect(find.text('${label.key}: ${model[label.value]}'), findsOneWidget);
    }
    await tapText(tester, 'Report sighting');
    final payload =
        jsonDecode(store.uploads.single.body) as Map<String, dynamic>;
    expect(payload['model'], model);
  });
}
