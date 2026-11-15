import 'dart:math' as math;
import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'package:weedz/inference/window_geometry.dart';

/// Bake EXIF orientation before any dimensions or boxes are used.
/// JPEG decoder differences have an explicit test tolerance. This does not
/// establish native tensor preprocessing or phone model parity.
img.Image decodeUpright(Uint8List bytes) {
  if (bytes.length > 50 * 1024 * 1024) {
    throw const FormatException('Image exceeds 50 MiB');
  }
  final decoder = img.findDecoderForData(bytes);
  final info = decoder?.startDecode(bytes);
  if (info == null ||
      info.width <= 0 ||
      info.height <= 0 ||
      info.width * info.height > 40000000 ||
      info.numFrames != 1) {
    throw const FormatException('A single frame within 40 MP is required');
  }
  final decoded = decoder!.decodeFrame(0);
  if (decoded == null) throw const FormatException('Unsupported image');
  final upright = img.bakeOrientation(decoded);
  return upright.convert(format: img.Format.uint8, numChannels: 3);
}

void _checkBox(img.Image image, PixelBox box) {
  if (box.left < 0 ||
      box.top < 0 ||
      box.right > image.width ||
      box.bottom > image.height ||
      box.left >= box.right ||
      box.top >= box.bottom) {
    throw ArgumentError('Box must be inside the upright image');
  }
}

/// Integer moments avoid scan-order error at the strict featureless boundary.
({int count, int sum, int squares}) _lumaMoments(
  img.Image image,
  PixelBox box,
) {
  _checkBox(image, box);
  var count = 0;
  var sum = 0;
  var squares = 0;
  for (var y = box.top; y < box.bottom; y++) {
    for (var x = box.left; x < box.right; x++) {
      final pixel = image.getPixel(x, y);
      final grey =
          (pixel.r.toInt() * 19595 +
              pixel.g.toInt() * 38470 +
              pixel.b.toInt() * 7471 +
              32768) >>
          16;
      count++;
      sum += grey;
      squares += grey * grey;
    }
  }
  return (count: count, sum: sum, squares: squares);
}

/// Population deviation of PIL-compatible integer luma before padding.
double greyscaleStd(img.Image image, PixelBox box) {
  final moments = _lumaMoments(image, box);
  final mean = moments.sum / moments.count;
  return math.sqrt(math.max(0, moments.squares / moments.count - mean * mean));
}

bool isFeatureless(img.Image image, PixelBox box) {
  final moments = _lumaMoments(image, box);
  // Compare variance < 8^2 exactly, without a rounded square root or 64-bit
  // overflow when multiplying moments of large, otherwise supported images.
  final count = BigInt.from(moments.count);
  final sum = BigInt.from(moments.sum);
  final varianceNumerator = BigInt.from(moments.squares) * count - sum * sum;
  return varianceNumerator < BigInt.from(64) * count * count;
}

/// Letterbox the exact crop; odd spare pixels go to the right and bottom.
img.Image squareWindow(img.Image image, PixelBox box) {
  _checkBox(image, box);
  final width = box.right - box.left;
  final height = box.bottom - box.top;
  final side = math.max(width, height);
  if (side * side > 40000000) {
    throw ArgumentError('Square window exceeds 40 MP');
  }
  final output = img.Image(width: side, height: side);
  img.fill(output, color: img.ColorRgb8(124, 116, 104));
  final dx = (side - width) ~/ 2;
  final dy = (side - height) ~/ 2;
  for (var y = 0; y < height; y++) {
    for (var x = 0; x < width; x++) {
      final pixel = image.getPixel(box.left + x, box.top + y);
      output.setPixelRgb(dx + x, dy + y, pixel.r, pixel.g, pixel.b);
    }
  }
  return output;
}
