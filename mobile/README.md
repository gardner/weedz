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
