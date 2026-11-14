import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';
import 'package:weedz/ui/theme.dart';

import '../../domain/fixtures.dart';

const foundId = '6f1c2a4e-8b3d-4c5e-9f70-1a2b3c4d5e6f';
const revisedId = '0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';

/// What the scan found: the fixture's crop and exact location.
Findings fullFindings() {
  final report = fullReport();
  return Findings(crop: report.image, location: report.location);
}

/// A freshly found report: the photo's location, and no photo consent yet.
ReportCase foundCase() =>
    ReportCase.found(id: foundId, report: fullReport().withoutImage());

/// Every choice made (photo under CC BY, exact location shared) and approved.
ReportCase approvedCase() =>
    ReportCase.found(id: foundId, report: fullReport()).approve();

ReportCase sendingCase() => approvedCase().startSending().$1;

ReportCase unansweredCase() => sendingCase().sendFailed();

ReportCase refusedCase() => sendingCase().refused();

ReportCase receivedCase() => sendingCase().received();

/// Stands in for the report store: it commits each transition the screen
/// asks for, and keeps what would have gone over the wire.
class FakeStore extends ChangeNotifier {
  new(this.current);

  ReportCase current;
  final changes = <ReportCase>[];
  final uploads = <Upload>[];
  final withdrawals = <ReportCase>[];
  ReportCase? retired;

  void change(ReportCase next) {
    changes.add(next);
    current = next;
    notifyListeners();
  }

  void send(ReportCase approved) {
    final (sending, upload) = approved.startSending();
    uploads.add(upload);
    change(sending);
  }

  void withdraw(ReportCase sent) {
    withdrawals.add(sent);
    change(sent.withdrawn());
  }

  void revise(ReportCase old, ReportCase fresh) {
    retired = old;
    change(fresh);
  }
}

/// Shows [initial] on the approval screen, backed by a [FakeStore].
Future<FakeStore> pumpApproval(
  WidgetTester tester,
  ReportCase initial, {
  Findings? findings,
  double textScale = 1,
  bool reduceMotion = false,
}) async {
  final store = FakeStore(initial);
  await tester.pumpWidget(
    MaterialApp(
      theme: appTheme(),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          textScaler: TextScaler.linear(textScale),
          disableAnimations: reduceMotion,
        ),
        child: child!,
      ),
      home: ListenableBuilder(
        listenable: store,
        builder: (context, _) => ApprovalScreen(
          reportCase: store.current,
          findings: findings ?? fullFindings(),
          onChanged: store.change,
          onSend: store.send,
          onWithdraw: store.withdraw,
          onRevised: store.revise,
          newId: () => revisedId,
        ),
      ),
    ),
  );
  return store;
}

/// Scrolls [text] into view and taps it. Pumps a fixed time rather than
/// settling, since a sending report shows an endless progress indicator.
Future<void> tapText(WidgetTester tester, String text) async {
  final target = find.text(text);
  await tester.ensureVisible(target);
  await tester.pump();
  await tester.tap(target);
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
}

/// The approve button, found by its label.
FilledButton approveButton(WidgetTester tester) => tester.widget<FilledButton>(
  find.widgetWithText(FilledButton, 'Approve this report'),
);

/// Answers every choice: send the photo under CC BY-NC, share the location.
Future<void> answerEverything(WidgetTester tester) async {
  await tapText(tester, 'Send this photo');
  await tapText(tester, licenceLabels['cc-by-nc']!);
  await tapText(tester, 'Share this exact location');
}
