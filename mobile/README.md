# Weedz mobile

The Flutter app (Android and iOS) that scans the phone's photo library for
likely weeds and sends only the reports its person approves. The architecture,
privacy properties and upload contract are in [docs/mobile.md](../docs/mobile.md).

```sh
flutter pub get
flutter analyze
flutter test
```

`lib/domain/` is pure Dart (no plugins or platform code), so its tests run
without a device.

Settings now supports secure pilot enrollment and restartable data deletion. See
[mobile device settings](../docs/mobile-device-settings.md) for the two required
deployment URL defines, the operator flow, and device verification still needed
before store release. This client does not upload reports.
