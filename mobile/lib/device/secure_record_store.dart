import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:weedz/device/device_record.dart';

/// Device-only Keychain on iOS, encrypted Keystore-backed storage on Android.
/// Credential preferences are excluded from Android backup and device transfer.
/// Plaintext tokens never enter app preferences.
final class SecureDeviceRecordStore implements DeviceRecordStore {
  const new();

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(
      storageNamespace: 'weedz.device',
      resetOnError: false,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.unlocked_this_device,
    ),
  );
  static const _key = 'weedz.device-enrollment.v1';

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String record) async {
    await _storage.write(key: _key, value: record);
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      // Plugin 11 returns after apply(); wait for its disk commit.
      await const MethodChannel('weedz/device-storage')
          .invokeMethod<void>('flush');
    }
  }
}
