import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import 'harness.dart';

void main() {
  testWidgets('a withdrawal confirmed after the send settles still goes '
      'through', (tester) async {
    final store = await pumpApproval(tester, sendingCase());
    await tapText(tester, 'Withdraw report');
    // The send is received while the person reads the dialog.
    store.change(sendingCase().received());
    await tester.pump();
    await tapText(tester, 'Withdraw');
    expect(store.withdrawals, hasLength(1));
    expect(store.current.status, ApprovalStatus.withdrawn);
  });

  testWidgets('a photo and location in the report but not in the findings '
      'are offered, and kept when chosen', (tester) async {
    final store = await pumpApproval(
      tester,
      ReportCase.found(id: foundId, report: approvedCase().report),
      findings: const Findings(),
    );
    await answerEverything(tester);
    await tapText(tester, 'Report sighting');
    final report = store.current.report;
    expect(store.current.status, ApprovalStatus.sending);
    expect(report.image, isNotNull);
    expect(report.location, isNotNull);
  });

  testWidgets('the photo preview is not reloaded on each choice', (
    tester,
  ) async {
    await pumpApproval(tester, foundCase());
    final before = tester.widget<Image>(find.byType(Image)).image;
    await tapText(tester, 'Send this photo');
    final after = tester.widget<Image>(find.byType(Image)).image;
    expect(identical(before, after), isTrue);
  });
}
