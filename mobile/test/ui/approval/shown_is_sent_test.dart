import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/ui/approval/approval_screen.dart';
import 'package:weedz/ui/theme.dart';

import 'harness.dart';

/// [foundCase] with its location's accuracy replaced.
ReportCase withAccuracy(double accuracyM) {
  final report = foundCase().report;
  final place = report.location!;
  return ReportCase.found(
    id: foundId,
    report: report.copyWith(
      location: Location(
        latitude: place.latitude,
        longitude: place.longitude,
        accuracyM: accuracyM,
      ),
    ),
  );
}

void main() {
  group('every detail sent is shown, unrounded, before approval', () {
    testWidgets('no credit name is sent by default', (tester) async {
      await pumpApproval(tester, foundCase());
      expect(find.textContaining('A. Contributor'), findsNothing);
    });

    testWidgets('removing the photo also removes the credit name', (
      tester,
    ) async {
      await pumpApproval(tester, approvedCase());
      await tapText(tester, "Don't send the photo");
      expect(find.textContaining('A. Contributor'), findsNothing);
    });

    testWidgets('the full capture time', (tester) async {
      await pumpApproval(tester, foundCase());
      expect(find.textContaining('2026-10-02T23:15:42.000Z'), findsOne);
    });

    for (final accuracy in [4.74, 0.04]) {
      testWidgets('an accuracy of $accuracy m', (tester) async {
        final reportCase = withAccuracy(accuracy);
        final findings = Findings(
          crop: fullFindings().crop,
          location: reportCase.report.location,
        );
        final handle = tester.ensureSemantics();
        await pumpApproval(tester, reportCase, findings: findings);
        expect(find.textContaining('±$accuracy m'), findsOne);
        expect(
          find.bySemanticsLabel(RegExp('within $accuracy metres')),
          findsOne,
        );
        handle.dispose();
      });
    }
  });

  testWidgets('a confirmation opened before the report moved on does '
      'nothing', (tester) async {
    final store = await pumpApproval(tester, sendingCase());
    await tapText(tester, 'Withdraw report');
    // The send is refused while the person reads the dialog.
    store.change(sendingCase().refused());
    await tester.pump();
    await tapText(tester, 'Withdraw');
    expect(tester.takeException(), isNull);
    expect(store.withdrawals, isEmpty);
    expect(store.current.status, ApprovalStatus.refused);
  });

  testWidgets('themed buttons fit side by side in a row', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: appTheme(),
        home: Scaffold(
          body: Row(
            children: [
              OutlinedButton(onPressed: () {}, child: const Text('Cancel')),
              FilledButton(onPressed: () {}, child: const Text('Save')),
            ],
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    expect(tester.getSize(find.byType(FilledButton)).height, 48);
  });
}
