import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/device/secure_record_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const barrier = MethodChannel('weedz/device-storage');

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(barrier, null);
  });

  test('Android secure write waits for the native disk barrier', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    FlutterSecureStorage.setMockInitialValues({});
    var committed = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(barrier, (call) async {
          expect(call.method, 'flush');
          expect(
            await const SecureDeviceRecordStore().read(),
            'pending-record',
          );
          committed = true;
          return null;
        });
    await const SecureDeviceRecordStore().write('pending-record');
    expect(committed, isTrue);
  });

  test(
    'commit failure prevents acknowledging a durable secure write',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      FlutterSecureStorage.setMockInitialValues({});
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(barrier, (_) async {
            throw PlatformException(code: 'storage');
          });
      await expectLater(
        const SecureDeviceRecordStore().write('pending-record'),
        throwsA(isA<PlatformException>()),
      );
    },
  );
}
