import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import 'harness.dart';

void main() {
  testWidgets('one action sends no photo and the visible recorded location', (
    tester,
  ) async {
    final store = await pumpApproval(tester, foundCase());
    expect(store.uploads, isEmpty);
    expect(find.textContaining('-41.2706319'), findsWidgets);
    expect(find.text('Licence for the photo'), findsNothing);
    await tapText(tester, 'Report sighting');
    final report = store.current.report;
    expect(store.current.status, ApprovalStatus.sending);
    expect(report.image, isNull);
    expect(report.consent.licence, isNull);
    expect(report.consent.uses, isEmpty);
    expect(report.consent.credit, isNull);
    expect(report.location, isNotNull);
    expect(report.consent.location, isTrue);
    expect(report.candidate.score, 0.051);
    expect(store.uploads, hasLength(1));
    final payload =
        jsonDecode(store.uploads.single.body) as Map<String, dynamic>;
    expect(payload.containsKey('image'), isFalse);
    final consent = payload['consent'] as Map<String, dynamic>;
    expect(consent, {
      'wording_version': '2026-11-15',
      'image': false,
      'location': true,
      'uses': <String>[],
    });
  });

  testWidgets('location opt-out is the payload sent by the same action', (
    tester,
  ) async {
    final store = await pumpApproval(tester, foundCase());
    await tapText(tester, 'Remove the location');
    await tapText(tester, 'Report sighting');
    final payload =
        jsonDecode(store.uploads.single.body) as Map<String, dynamic>;
    expect(payload.containsKey('location'), isFalse);
    expect((payload['consent'] as Map<String, dynamic>)['location'], isFalse);
    expect(store.current.report.consent.credit, isNull);
  });

  testWidgets(
    'approved snapshot needs no parent rebuild and rapid taps send once',
    (tester) async {
      final sent = <ReportCase>[];
      await tester.pumpWidget(
        MaterialApp(
          home: ApprovalScreen(
            reportCase: foundCase(),
            findings: fullFindings(),
            onChanged: (_) {},
            onSend: sent.add,
            onWithdraw: (_) {},
            onRevised: (_, _) {},
          ),
        ),
      );
      final button = find.widgetWithText(FilledButton, 'Report sighting');
      await tester.ensureVisible(button);
      final request = tester.widget<FilledButton>(button).onPressed!;
      request();
      request();
      await tester.pump();
      expect(sent, hasLength(1));
      expect(sent.single.status, ApprovalStatus.approved);
      expect(sent.single.startSending().$2, isNotNull);
      expect(find.text('Reporting…'), findsOneWidget);
    },
  );
  testWidgets(
    'callback failure keeps uncertain snapshot locked until reconciled',
    (tester) async {
      var calls = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: ApprovalScreen(
            reportCase: foundCase(),
            findings: fullFindings(),
            onChanged: (_) {},
            onSend: (_) {
              calls++;
              throw StateError('store unavailable');
            },
            onWithdraw: (_) {},
            onRevised: (_, _) {},
          ),
        ),
      );
      final button = find.widgetWithText(FilledButton, 'Report sighting');
      await tester.ensureVisible(button);
      final request = tester.widget<FilledButton>(button).onPressed!;
      expect(request, throwsStateError);
      request();
      await tester.pump();
      expect(calls, 1);
      expect(
        find.textContaining('Report status is unconfirmed'),
        findsOneWidget,
      );
      expect(find.text('Report sighting'), findsNothing);
    },
  );
}
