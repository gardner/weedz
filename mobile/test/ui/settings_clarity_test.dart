import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/ui/device_settings.dart';

import '../device/fakes.dart' as fixtures;

void main() {
  testWidgets(
    'saved state is truthful and connection details start collapsed',
    (tester) async {
      final store = fixtures.MemoryStore();
      final controller = DeviceDeletion(
        store: store,
        api: fixtures.FakeDeletion(store),
      );
      await controller.load();
      await controller.enroll(fixtures.enrollment);
      await tester.pumpWidget(
        MaterialApp(home: DeviceSettings(controller: controller)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Enrollment saved'), findsOneWidget);
      expect(find.text('Connected'), findsNothing);
      expect(find.textContaining('https://intake.example.test'), findsNothing);
      expect(
        find.text(
          'Delete your shared sightings. Originals stay on your phone.',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('credential hash'), findsNothing);
      await tester.tap(find.text('Connection details'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('https://intake.example.test'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'expanded connection does not expand reenrollment after deletion',
    (tester) async {
      final store = fixtures.MemoryStore();
      final controller = DeviceDeletion(
        store: store,
        api: fixtures.FakeDeletion(store),
      );
      await controller.load();
      await controller.enroll(fixtures.enrollment);
      await tester.pumpWidget(
        MaterialApp(home: DeviceSettings(controller: controller)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Connection details'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete my data'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete reports and revoke access'));
      await tester.pumpAndSettle();
      expect(find.text('Deletion confirmed'), findsOneWidget);
      expect(find.text('Set up another enrollment'), findsOneWidget);
      expect(find.text('Submitter token'), findsNothing);
    },
  );

  testWidgets(
    'material deletion disclosures are available and shown before confirmation',
    (tester) async {
      final store = fixtures.MemoryStore();
      final api = fixtures.FakeDeletion(store);
      final controller = DeviceDeletion(store: store, api: api);
      await controller.load();
      await controller.enroll(fixtures.enrollment);
      await tester.pumpWidget(
        MaterialApp(home: DeviceSettings(controller: controller)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('What deletion removes'));
      await tester.pumpAndSettle();
      expect(find.textContaining('credential hash'), findsOneWidget);
      await tester.ensureVisible(find.text('Delete my data'));
      await tester.tap(find.text('Delete my data'));
      await tester.pumpAndSettle();
      expect(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.textContaining('credential hash'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.textContaining('backups'),
        ),
        findsOneWidget,
      );
      expect(api.calls, 0);
    },
  );
}
