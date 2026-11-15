import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:weedz/inference/image_windows.dart';

void main() {
  test('balanced boundary values remain eligible for every scan length', () {
    for (var count = 2; count <= 400; count += 2) {
      final image = img.Image(width: count, height: 1);
      for (var x = 0; x < count; x++) {
        final value = x < count ~/ 2 ? 112 : 128;
        image.setPixelRgb(x, 0, value, value, value);
      }
      expect(
        greyscaleStd(image, (left: 0, top: 0, right: count, bottom: 1)),
        8,
      );
      expect(
        isFeatureless(image, (left: 0, top: 0, right: count, bottom: 1)),
        isFalse,
        reason: 'count=$count',
      );
    }
  });
}
