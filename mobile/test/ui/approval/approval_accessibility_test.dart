import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';

import 'harness.dart';

/// Every state the screen can show, by name.
Map<String, ReportCase Function()> get everyState => {
  'pending': foundCase,
  'approved': approvedCase,
  'sending': sendingCase,
  'unanswered': unansweredCase,
  'refused': refusedCase,
  'received': receivedCase,
  'withdrawn': () => receivedCase().withdrawn(),
  'declined': () => foundCase().decline(),
};

/// A small phone: 360 × 640 logical pixels.
void useSmallPhone(WidgetTester tester) {
  tester.view
    ..physicalSize = const Size(1080, 1920)
    ..devicePixelRatio = 3;
  addTearDown(tester.view.reset);
}

void main() {
  group('the exact location', () {
    testWidgets('is shown as coordinates with its accuracy', (tester) async {
      await pumpApproval(tester, foundCase());
      expect(find.textContaining('-41.2706319'), findsWidgets);
      expect(find.textContaining('173.2839653'), findsWidgets);
      expect(find.textContaining('4.7 m'), findsWidgets);
      expect(find.textContaining('where the camera was'), findsOne);
    });

    testWidgets('is announced to screen readers as one sentence', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await pumpApproval(tester, foundCase());
      expect(
        find.bySemanticsLabel(
          'Exact location in this report: latitude -41.2706319, '
          'longitude 173.2839653, accurate to within 4.7 metres.',
        ),
        findsOne,
      );
      handle.dispose();
    });
  });

  testWidgets('the status is a live region with words, not just colour', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final store = await pumpApproval(tester, foundCase());
    expect(
      tester.getSemantics(find.byKey(const Key('approval-status'))),
      containsSemantics(
        isLiveRegion: true,
        label: 'Waiting for your decision',
      ),
    );
    expect(find.byIcon(Icons.hourglass_empty), findsOne);

    store.change(approvedCase());
    await tester.pump();
    expect(
      tester.getSemantics(find.byKey(const Key('approval-status'))),
      containsSemantics(isLiveRegion: true, label: 'Approved: ready to send'),
    );
    handle.dispose();
  });

  testWidgets('section titles are headings', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpApproval(tester, foundCase());
    for (final title in ['Suggested weed', 'Location', 'Photo']) {
      expect(
        tester.getSemantics(find.text(title)),
        containsSemantics(isHeader: true),
        reason: title,
      );
    }
    handle.dispose();
  });

  testWidgets('reduced motion replaces the spinning progress indicator', (
    tester,
  ) async {
    await pumpApproval(tester, sendingCase(), reduceMotion: true);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('Sending…'), findsOne);
  });

  for (final MapEntry(key: name, value: makeCase) in everyState.entries) {
    group('when $name', () {
      testWidgets('meets the tap target, label and contrast guidelines', (
        tester,
      ) async {
        final handle = tester.ensureSemantics();
        useSmallPhone(tester);
        await pumpApproval(tester, makeCase(), reduceMotion: true);
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        handle.dispose();
      });

      testWidgets('lays out at a text scale of 2.0 on a small phone', (
        tester,
      ) async {
        useSmallPhone(tester);
        await pumpApproval(
          tester,
          makeCase(),
          textScale: 2,
          reduceMotion: true,
        );
        expect(tester.takeException(), isNull);
        // Everything is reachable by scrolling, down to the last action.
        await tester.dragUntilVisible(
          find.byKey(const Key('approval-end')),
          find.byType(Scrollable).first,
          const Offset(0, -300),
        );
        expect(tester.takeException(), isNull);
      });
    });
  }

  testWidgets('pending choices meet the guidelines once answered', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    useSmallPhone(tester);
    await pumpApproval(tester, foundCase(), textScale: 2);
    await answerEverything(tester);
    expect(tester.takeException(), isNull);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });
}
