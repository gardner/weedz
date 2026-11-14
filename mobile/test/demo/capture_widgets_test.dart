/// Opt-in captures of production widgets, with clearly marked synthetic state.
/// Run only with WEEDZ_CAPTURE_DIR and WEEDZ_DEMO_IMAGE outside git.
library;

import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/device_record.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/ui/approval/approval_screen.dart';
import 'package:weedz/ui/device_settings.dart';
import 'package:weedz/ui/theme.dart';

final String? _output = Platform.environment['WEEDZ_CAPTURE_DIR'];
final String? _image = Platform.environment['WEEDZ_DEMO_IMAGE'];
final GlobalKey<State<StatefulWidget>> _boundary = GlobalKey();

class _MemoryRecord implements DeviceRecordStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String record) async => value = record;
}

class _NoNetwork implements DeleteSubmitter {
  @override
  Future<DeletionReceipt> delete(DeviceEnrollment device) async =>
      throw const DeletionFailure(DeletionProblem.unconfirmed);
  @override
  void close() {}
}

Widget _frame(
  Widget child, {
  String label = 'PROTOTYPE DEMO · PUBLIC PHOTO · NO UPLOAD',
}) => MaterialApp(
  theme: appTheme(),
  builder: (context, child) => RepaintBoundary(
    key: _boundary,
    child: Column(
      children: [
        Container(
          width: double.infinity,
          color: const Color(0xff163f30),
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontFamily: 'Roboto',
              fontSize: 11,
              color: Color(0xffeef5e9),
              decoration: TextDecoration.none,
            ),
          ),
        ),
        Expanded(child: child!),
      ],
    ),
  ),
  home: child,
);

Future<void> _save(WidgetTester tester, String name) async {
  await tester.pumpAndSettle();
  await tester.runAsync(() async {
    final render =
        _boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final image = await render.toImage(pixelRatio: 2);
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    await File('$_output/$name.png').writeAsBytes(data!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  testWidgets('capture real approval and deletion widgets', (tester) async {
    final output = Directory(_output!).absolute;
    expect(output.path.contains('/weedz-demo-artifacts/'), isTrue);
    output.createSync(recursive: true);
    tester.view.physicalSize = const Size(1080, 2160);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final sdk = Platform.environment['WEEDZ_FLUTTER_SDK']!;
    final loader = FontLoader('Roboto')
      ..addFont(
        Future.value(
          ByteData.sublistView(
            File(
              '$sdk/bin/cache/artifacts/material_fonts/Roboto-Regular.ttf',
            ).readAsBytesSync(),
          ),
        ),
      );
    await tester.runAsync(loader.load);
    final icons = FontLoader('MaterialIcons')
      ..addFont(
        Future.value(
          ByteData.sublistView(
            File(
              '$sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
            ).readAsBytesSync(),
          ),
        ),
      );
    await tester.runAsync(icons.load);
    final crop = Crop.fromBytes(File(_image!).readAsBytesSync());
    var current = ReportCase.found(
      id: 'e9fa2241-6f9f-4d58-bac9-112000000001',
      report: Report(
        appVersion: '0.1.0+1',
        candidate: Candidate(taxon: 'Ulex europaeus', score: 0.055046),
        model: Screening(
          modelKey: 'bioclip-2',
          revision: '2957b322090f9cb17ae72c71981c7218a28d81e0',
          rankingRevision: 4,
          scoreMeaning: 'bioclip-2/ranking-4/meaning-1',
        ),
        consent: Consent(
          wordingVersion: '2026-11',
          image: false,
          location: false,
        ),
      ),
    );
    late StateSetter rebuild;
    await tester.pumpWidget(
      _frame(
        StatefulBuilder(
          builder: (context, setState) {
            rebuild = setState;
            return ApprovalScreen(
              reportCase: current,
              findings: Findings(crop: crop),
              onChanged: (next) => rebuild(() => current = next),
              onSend: (_) => throw StateError('Demo must never send a report'),
              onWithdraw: (_) =>
                  throw StateError('Demo must never send a withdrawal'),
              onRevised: (_, _) => throw StateError('Demo must never revise'),
            );
          },
        ),
      ),
    );
    await tester.runAsync(() async {
      await precacheImage(MemoryImage(crop.bytes), _boundary.currentContext!);
    });
    await _save(tester, 'flutter-approval-photo');
    await tester.ensureVisible(find.text('Send this photo'));
    await tester.tap(find.text('Send this photo'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text(licenceLabels['cc-by']!));
    await tester.tap(find.text(licenceLabels['cc-by']!));
    await tester.pumpAndSettle();
    await _save(tester, 'flutter-approval-choices');
    await tester.ensureVisible(find.text('Approve this report'));
    await tester.tap(find.text('Approve this report'));
    await tester.pumpAndSettle();
    await _save(tester, 'flutter-approval-approved');

    final store = _MemoryRecord();
    final deletion = DeviceDeletion(store: store, api: _NoNetwork());
    await deletion.load();
    await deletion.enroll(
      DeviceEnrollment(
        server: 'https://intake.example.invalid',
        token: 'weedzsub_1_${'DEMO_NOT_A_REAL_SECRET_' * 2}',
      ),
    );
    await tester.pumpWidget(
      _frame(
        DeviceSettings(
          controller: deletion,
        ),
        label: 'PROTOTYPE DEMO · TEST ENROLLMENT · NO NETWORK',
      ),
    );
    await _save(tester, 'flutter-settings-delete');
    await tester.tap(find.text('Delete my data'));
    await _save(tester, 'flutter-settings-confirmation');
    await tester.tap(find.text('Delete reports and revoke access'));
    await _save(tester, 'flutter-settings-pending');
    deletion.dispose();
  }, skip: _output == null || _image == null);
}
