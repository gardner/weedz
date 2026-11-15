import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import '../../domain/fixtures.dart';
import 'harness.dart';

void main() {
  testWidgets('real decoder failure removes an attached unreadable crop', (
    tester,
  ) async {
    final store = await pumpApproval(
      tester,
      approvedCase(),
      findings: Findings(crop: jpegCrop()),
    );
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump();
    await tester.pump();
    expect(
      find.text('The photo could not be shown. It cannot be attached.'),
      findsOneWidget,
    );
    expect(find.text('Send this photo'), findsNothing);
    expect(store.current.status, ApprovalStatus.pending);
    expect(store.current.report.image, isNull);
    await tapText(tester, 'Report sighting');
    expect(store.current.report.image, isNull);
    expect(store.current.report.consent.credit, isNull);
  });
}
