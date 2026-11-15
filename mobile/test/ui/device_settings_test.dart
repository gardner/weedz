import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/deployment.dart';
import 'package:weedz/ui/device_settings.dart';

import '../device/fakes.dart' as fixtures;

void main() {
  testWidgets(
    'pilot enrollment saves the hidden token without a network call',
    (tester) async {
      final store = fixtures.MemoryStore();
      final api = fixtures.FakeDeletion(store);
      final controller = DeviceDeletion(store: store, api: api);
      await tester.pumpWidget(
        MaterialApp(
          home: DeviceSettings(
            controller: controller,
            deployment: const DeviceDeployment(
              intakeBaseUrl: 'https://intake.example.test/pilot/',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Keep this token private.'), findsOneWidget);
      final tokenField = find.widgetWithText(TextField, 'Submitter token');
      expect(tester.widget<TextField>(tokenField).obscureText, isTrue);
      await tester.enterText(tokenField, fixtures.enrollment.token);
      await tester.scrollUntilVisible(
        find.text('Save enrollment securely'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Save enrollment securely'));
      await tester.pumpAndSettle();
      expect(store.value, contains(fixtures.enrollment.token));
      expect(api.calls, 0);
      expect(find.text('Delete my data'), findsOneWidget);
      expect(find.text(fixtures.enrollment.token), findsNothing);
    },
  );

  testWidgets(
    'confirmation, recoverable pending state and completion are accessible',
    (tester) async {
      final store = fixtures.MemoryStore();
      final api = fixtures.FakeDeletion(store)..fail = true;
      final controller = DeviceDeletion(store: store, api: api);
      await controller.load();
      await controller.enroll(fixtures.enrollment);
      await tester.pumpWidget(
        MaterialApp(home: DeviceSettings(controller: controller)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete my data'));
      await tester.pumpAndSettle();
      expect(find.text('Delete all reports from this phone?'), findsOneWidget);
      expect(api.calls, 0);
      await tester.tap(find.text('Keep my data'));
      await tester.pumpAndSettle();
      expect(api.calls, 0);
      await tester.tap(find.text('Delete my data'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete reports and revoke access'));
      await tester.pumpAndSettle();
      expect(find.text('Deletion not yet confirmed'), findsOneWidget);
      expect(find.text('Retry deletion'), findsOneWidget);
      expect(store.value, contains(fixtures.enrollment.token));
      expect(find.text(fixtures.enrollment.token), findsNothing);
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
      api.fail = false;
      await tester.tap(find.text('Retry deletion'));
      await tester.pumpAndSettle();
      expect(find.text('Deletion confirmed'), findsOneWidget);
      expect(store.value, isNot(contains(fixtures.enrollment.token)));
    },
  );

  testWidgets('pending flow remains usable with large text', (tester) async {
    final store = fixtures.MemoryStore();
    final api = fixtures.FakeDeletion(store)..fail = true;
    final controller = DeviceDeletion(store: store, api: api);
    await controller.load();
    await controller.enroll(fixtures.enrollment);
    await controller.delete();
    await tester.pumpWidget(
      MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: const TextScaler.linear(2)),
          child: child!,
        ),
        home: DeviceSettings(controller: controller),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Retry deletion'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(tester.takeException(), isNull);
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  });

  testWidgets(
    'public request route uses deployment configuration and no credential',
    (tester) async {
      final store = fixtures.MemoryStore();
      final controller = DeviceDeletion(
        store: store,
        api: fixtures.FakeDeletion(store),
      );
      Uri? opened;
      await tester.pumpWidget(
        MaterialApp(
          home: DeviceSettings(
            controller: controller,
            deployment: const DeviceDeployment(
              deletionRequestUrl: 'https://publisher.example.test/delete',
            ),
            openRoute: (uri) async {
              opened = uri;
              return true;
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Help'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Help'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Request deletion without this phone'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Request deletion without this phone'));
      await tester.pumpAndSettle();
      expect(opened.toString(), 'https://publisher.example.test/delete');
      expect(find.text('Deletion confirmed'), findsNothing);
    },
  );
}
