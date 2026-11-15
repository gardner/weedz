import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/ui/approval/approval_screen.dart';

import 'harness.dart';

void main() {
  testWidgets(
    'coalesced immediate retry failure restores retry and withdrawal',
    (tester) async {
      final state = ValueNotifier<ReportCase>(unansweredCase());
      addTearDown(state.dispose);
      final bodies = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: ValueListenableBuilder(
            valueListenable: state,
            builder: (context, current, _) => ApprovalScreen(
              reportCase: current,
              findings: fullFindings(),
              onChanged: (next) => state.value = next,
              onSend: (approved) {
                final (sending, upload) = approved.startSending();
                bodies.add(upload.body);
                state
                  ..value = sending
                  ..value = sending.sendFailed();
              },
              onWithdraw: (sent) => state.value = sent.withdrawn(),
              onRevised: (_, _) {},
            ),
          ),
        ),
      );
      await tapText(tester, 'Send again unchanged');
      expect(find.text('Send again unchanged'), findsOneWidget);
      expect(find.text('Withdraw report'), findsOneWidget);
      expect(find.text('Reporting…'), findsNothing);
      await tapText(tester, 'Send again unchanged');
      expect(bodies, hasLength(2));
      expect(bodies[0], bodies[1]);
      expect(bodies[0], unansweredCase().startSending().$2.body);
    },
  );
}
