import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';

import 'harness.dart';

void main() {
  group('a sent report is frozen', () {
    testWidgets('its choices can no longer be changed', (tester) async {
      await pumpApproval(tester, receivedCase());
      expect(find.text('Send this photo'), findsNothing);
      expect(find.text('Remove the location'), findsNothing);
      expect(find.text('Approve this report'), findsNothing);
      expect(find.textContaining('-41.2706319'), findsWidgets);
    });

    testWidgets('a sending report shows progress and can be withdrawn', (
      tester,
    ) async {
      await pumpApproval(tester, sendingCase());
      expect(find.text('Sending…'), findsOne);
      expect(find.byType(CircularProgressIndicator), findsOne);
      expect(find.text('Withdraw report'), findsOne);
    });
  });

  group('unanswered', () {
    testWidgets('says it may have arrived, and offers to send again or '
        'withdraw', (tester) async {
      final store = await pumpApproval(tester, unansweredCase());
      expect(find.text('No answer from the server'), findsOne);
      expect(find.textContaining('may already have it'), findsOne);
      expect(find.text('Withdraw report'), findsOne);

      await tapText(tester, 'Send again unchanged');
      final upload = store.uploads.single;
      expect(upload.id, foundId);
      expect(upload.body, approvedCase().startSending().$2.body);
      expect(store.current.status, ApprovalStatus.sending);
    });
  });

  group('refused', () {
    testWidgets('explains, and offers revise or decline', (tester) async {
      await pumpApproval(tester, refusedCase());
      expect(find.text('The server refused this report'), findsOne);
      expect(find.textContaining('never be sent again as it is'), findsOne);
      expect(find.text('Revise without the photo'), findsOne);
      expect(find.text('Revise without the capture time'), findsOne);
      expect(find.text('Decline'), findsOne);
      expect(find.text('Send again unchanged'), findsNothing);
    });

    testWidgets('revising makes a new pending report under a new id', (
      tester,
    ) async {
      final store = await pumpApproval(tester, refusedCase());
      await tapText(tester, 'Revise without the photo');

      expect(store.retired?.status, ApprovalStatus.revised);
      expect(store.current.id, revisedId);
      expect(store.current.status, ApprovalStatus.pending);
      expect(store.current.report.image, isNull);
      // The person's choices carry over, adjusted for the removed photo.
      expect(approveButton(tester).onPressed, isNotNull);
      expect(find.text('Send report'), findsNothing);
    });
  });

  group('withdrawal', () {
    testWidgets('a received report can be withdrawn after confirming', (
      tester,
    ) async {
      final store = await pumpApproval(tester, receivedCase());
      expect(find.text('Sent: the server has this report'), findsOne);

      await tapText(tester, 'Withdraw report');
      expect(find.text('Withdraw this report?'), findsOne);
      await tapText(tester, 'Keep it');
      expect(store.withdrawals, isEmpty);

      await tapText(tester, 'Withdraw report');
      await tapText(tester, 'Withdraw');
      expect(store.withdrawals.single.id, foundId);
      expect(store.current.status, ApprovalStatus.withdrawn);
      expect(find.text('Withdrawn'), findsOne);
      expect(find.text('Withdraw report'), findsNothing);
    });

    testWidgets('an unanswered report can be withdrawn', (tester) async {
      final store = await pumpApproval(tester, unansweredCase());
      await tapText(tester, 'Withdraw report');
      await tapText(tester, 'Withdraw');
      expect(store.withdrawals, hasLength(1));
    });
  });

  testWidgets('final states offer no actions', (tester) async {
    for (final reportCase in [
      foundCase().decline(),
      receivedCase().withdrawn(),
      refusedCase()
          .revise(
            id: revisedId,
            report: refusedCase().report.withoutImage(),
          )
          .$1,
    ]) {
      await pumpApproval(tester, reportCase);
      expect(find.byType(FilledButton), findsNothing);
      expect(find.byType(OutlinedButton), findsNothing);
    }
  });
}
