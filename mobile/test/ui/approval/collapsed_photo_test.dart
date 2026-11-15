import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import '../../domain/fixtures.dart';
import 'harness.dart';

void main() {
  testWidgets('collapsed photo panel still discloses attachment and licence', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final store = await pumpApproval(
      tester,
      ReportCase.found(id: foundId, report: minimalReport()),
      findings: Findings(crop: fullFindings().crop),
    );
    await tapText(tester, 'Send this photo');
    await tapText(tester, licenceLabels['cc-by']!);
    await tapText(tester, 'Attach a photo (optional)');
    final summary = 'Photo attached under ${licenceLabels['cc-by']}.';
    expect(find.text(summary), findsOneWidget);
    expect(
      find.bySemanticsLabel(RegExp(RegExp.escape(summary))),
      findsOneWidget,
    );
    expect(find.text('Licence for the photo'), findsNothing);
    expect(find.textContaining('A. Contributor'), findsNothing);
    await tapText(tester, 'Report sighting');
    expect(store.current.report.image, isNotNull);
    expect(store.current.report.consent.licence, 'cc-by');
    expect(store.current.report.consent.credit, isNull);
    semantics.dispose();
  });
  testWidgets('opt-out summary overrides a retained licence when collapsed', (
    tester,
  ) async {
    final store = await pumpApproval(tester, approvedCase());
    await tapText(tester, "Don't send the photo");
    await tapText(tester, 'Attach a photo (optional)');
    expect(find.text('No photo will be sent.'), findsOneWidget);
    expect(find.textContaining('Photo attached under'), findsNothing);
    await tapText(tester, 'Report sighting');
    expect(store.current.report.image, isNull);
    expect(store.current.report.consent.licence, isNull);
    expect(store.current.report.consent.credit, isNull);
  });
}
