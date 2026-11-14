import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import 'harness.dart';

void main() {
  group('a report is not sendable until approved', () {
    testWidgets('a found report offers no way to send it', (tester) async {
      await pumpApproval(tester, foundCase());
      expect(find.text('Send report'), findsNothing);
      expect(find.text('Waiting for your decision'), findsOneWidget);
    });

    testWidgets('approving reveals Send, and Send sends that exact report', (
      tester,
    ) async {
      final store = await pumpApproval(tester, foundCase());
      await answerEverything(tester);
      await tapText(tester, 'Approve this report');

      expect(store.current.status, ApprovalStatus.approved);
      expect(find.text('Send report'), findsOneWidget);

      await tapText(tester, 'Send report');
      expect(store.uploads, hasLength(1));
      final body =
          jsonDecode(store.uploads.single.body) as Map<String, Object?>;
      expect(body['location'], {
        'latitude': -41.2706319,
        'longitude': 173.2839653,
        'accuracy_m': 4.7,
      });
      expect((body['consent']! as Map<String, Object?>)['licence'], 'cc-by-nc');
      expect(body['image'], isNotNull);
      expect(store.current.status, ApprovalStatus.sending);
    });

    testWidgets('declining is final and asks first', (tester) async {
      final store = await pumpApproval(tester, foundCase());
      await tapText(tester, 'Decline');
      await tapText(tester, 'Keep deciding');
      expect(store.current.status, ApprovalStatus.pending);

      await tapText(tester, 'Decline');
      await tapText(tester, 'Decline report');
      expect(store.current.status, ApprovalStatus.declined);
      expect(find.text('Approve this report'), findsNothing);
      expect(find.text('Send report'), findsNothing);
    });
  });

  group('an edit resets approval', () {
    testWidgets('changing the licence after approving needs approval again', (
      tester,
    ) async {
      final store = await pumpApproval(tester, approvedCase());
      expect(find.text('Send report'), findsOneWidget);

      await tapText(tester, licenceLabels['cc0']!);

      expect(store.current.status, ApprovalStatus.pending);
      expect(store.current.report.consent.licence, 'cc0');
      expect(find.text('Send report'), findsNothing);
      expect(approveButton(tester).onPressed, isNotNull);
    });

    testWidgets('removing the location takes it out of the report', (
      tester,
    ) async {
      final store = await pumpApproval(tester, approvedCase());
      await tapText(tester, 'Remove the location');

      expect(store.current.status, ApprovalStatus.pending);
      expect(store.current.report.location, isNull);
      expect(find.textContaining('-41.2706319'), findsNothing);
      expect(find.text('Location removed. It will not be sent.'), findsOne);
    });

    testWidgets('not sending the photo takes it and its licence out', (
      tester,
    ) async {
      final store = await pumpApproval(tester, approvedCase());
      await tapText(tester, "Don't send the photo");

      final report = store.current.report;
      expect(store.current.status, ApprovalStatus.pending);
      expect(report.image, isNull);
      expect(report.consent.image, isFalse);
      expect(report.consent.licence, isNull);
      expect(find.text(licenceLabels['cc-by']!), findsNothing);
    });
  });

  group('consent choices are required and explicit', () {
    testWidgets('nothing is chosen for the person', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpApproval(tester, foundCase());

      for (final label in [
        'Send this photo',
        "Don't send the photo",
        'Share this exact location',
        'Remove the location',
      ]) {
        expect(
          tester.getSemantics(find.text(label)),
          isSemantics(hasCheckedState: true, isChecked: false),
          reason: label,
        );
      }
      expect(find.byType(Checkbox), findsNothing);
      expect(approveButton(tester).onPressed, isNull);
      expect(find.text('Answer every choice above to approve.'), findsOne);
      handle.dispose();
    });

    testWidgets('sending the photo needs a licence chosen too', (tester) async {
      await pumpApproval(tester, foundCase());
      await tapText(tester, 'Send this photo');
      await tapText(tester, 'Share this exact location');
      expect(approveButton(tester).onPressed, isNull);

      await tapText(tester, licenceLabels['cc-by']!);
      expect(approveButton(tester).onPressed, isNotNull);
      expect(find.text('Answer every choice above to approve.'), findsNothing);
    });

    testWidgets('the choices are applied before approval, so what is shown '
        'is what is sent', (tester) async {
      final store = await pumpApproval(tester, foundCase());
      await tapText(tester, "Don't send the photo");
      await tapText(tester, 'Remove the location');

      final report = store.current.report;
      expect(store.current.status, ApprovalStatus.pending);
      expect(report.image, isNull);
      expect(report.location, isNull);
      expect(approveButton(tester).onPressed, isNotNull);
    });

    testWidgets('a report with nothing to choose says what will not be sent', (
      tester,
    ) async {
      await pumpApproval(
        tester,
        ReportCase.found(
          id: foundId,
          report: foundCase().report.withoutLocation(),
        ),
        findings: const Findings(),
      );
      expect(find.text('Send this photo'), findsNothing);
      expect(find.text('Share this exact location'), findsNothing);
      expect(
        find.textContaining('no location with a known accuracy'),
        findsOne,
      );
      expect(find.textContaining('no photo to send'), findsOne);
      expect(approveButton(tester).onPressed, isNotNull);
    });
  });

  testWidgets('the suggestion is a suggestion, with an honest score meaning', (
    tester,
  ) async {
    await pumpApproval(tester, foundCase());
    expect(find.textContaining('Clematis vitalba'), findsWidgets);
    expect(find.textContaining("old man's beard"), findsWidgets);
    expect(find.textContaining('not an identification'), findsOne);
    expect(find.textContaining('not a probability'), findsOne);
    expect(find.textContaining('bioclip-2/ranking-4/meaning-1'), findsOne);
  });

  testWidgets('an undeclared score meaning is said plainly', (tester) async {
    final base = foundCase().report;
    final report = Report(
      appVersion: base.appVersion,
      candidate: base.candidate,
      model: Screening(
        modelKey: 'bioclip-2',
        revision: base.model.revision,
        rankingRevision: 5,
      ),
      consent: base.consent,
      location: base.location,
    );
    await pumpApproval(tester, ReportCase.found(id: foundId, report: report));
    expect(find.textContaining('No meaning has been declared'), findsOne);
  });
}
