import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import '../../domain/fixtures.dart';

import 'harness.dart';

void main() {
  testWidgets(
    'location edit before attachment preserves supplied photo credit',
    (tester) async {
      final original = fullFindings();
      final store = await pumpApproval(
        tester,
        foundCase(),
        findings: Findings(crop: original.crop, location: original.location),
      );
      await tapText(tester, 'Remove the location');
      expect(store.current.report.consent.credit, isNull);
      await answerEverything(tester);
      expect(find.textContaining('A. Contributor'), findsOneWidget);
      await tapText(tester, 'Report sighting');
      final body =
          jsonDecode(store.uploads.single.body) as Map<String, dynamic>;
      expect(
        (body['consent'] as Map<String, dynamic>)['credit'],
        'A. Contributor',
      );
    },
  );

  testWidgets(
    'switching photo off and on preserves credit only when attached',
    (tester) async {
      final store = await pumpApproval(tester, approvedCase());
      await tapText(tester, "Don't send the photo");
      expect(store.current.report.consent.credit, isNull);
      expect(find.textContaining('A. Contributor'), findsNothing);
      await tapText(tester, 'Send this photo');
      expect(find.textContaining('A. Contributor'), findsOneWidget);
      await tapText(tester, 'Report sighting');
      expect(store.current.report.consent.credit, 'A. Contributor');
    },
  );
  testWidgets('reopening draft can restore locally retained supplied credit', (
    tester,
  ) async {
    final findings = fullFindings();
    final original = await pumpApproval(
      tester,
      foundCase(),
      findings: findings,
    );
    await tapText(tester, 'Remove the location');
    expect(original.current.report.consent.credit, isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    final reopened = await pumpApproval(
      tester,
      original.current,
      findings: findings,
    );
    await answerEverything(tester);
    await tapText(tester, 'Report sighting');
    expect(reopened.current.report.consent.credit, 'A. Contributor');
  });

  testWidgets('cached credit is not inherited by another case id', (
    tester,
  ) async {
    await pumpApproval(tester, foundCase());
    final fresh = await pumpApproval(
      tester,
      ReportCase.found(id: revisedId, report: minimalReport()),
      findings: Findings(crop: fullFindings().crop),
    );
    await tapText(tester, 'Send this photo');
    await tapText(tester, licenceLabels['cc-by']!);
    expect(find.textContaining('A. Contributor'), findsNothing);
    await tapText(tester, 'Report sighting');
    expect(fresh.current.report.consent.credit, isNull);
  });
}
