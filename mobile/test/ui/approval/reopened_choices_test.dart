import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';

import 'harness.dart';

void main() {
  testWidgets('reopening pending report preserves explicit location removal', (
    tester,
  ) async {
    final original = await pumpApproval(tester, foundCase());
    await tapText(tester, 'Remove the location');
    expect(original.current.status, ApprovalStatus.pending);
    await tester.pumpWidget(const SizedBox.shrink());
    final reopened = await pumpApproval(tester, original.current);
    expect(find.textContaining('-41.2706319'), findsNothing);
    await tapText(tester, 'Report sighting');
    expect(reopened.current.report.location, isNull);
    expect(reopened.current.report.consent.location, isFalse);
  });

  testWidgets('reopening pending report preserves chosen photo and licence', (
    tester,
  ) async {
    final original = await pumpApproval(tester, foundCase());
    await answerEverything(tester);
    expect(original.current.status, ApprovalStatus.pending);
    await tester.pumpWidget(const SizedBox.shrink());
    final reopened = await pumpApproval(tester, original.current);
    expect(find.text('Licence for the photo'), findsOneWidget);
    await tapText(tester, 'Report sighting');
    expect(reopened.current.report.image, original.current.report.image);
    expect(reopened.current.report.consent.licence, 'cc-by-nc');
  });
}
