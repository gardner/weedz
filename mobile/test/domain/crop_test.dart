import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/crop.dart';

Uint8List bytes(List<int> header, [int size = 0]) {
  return Uint8List(header.length > size ? header.length : size)
    ..setAll(0, header);
}

const jpeg = [0xFF, 0xD8, 0xFF, 0xE0];
const png = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
// "RIFF", a length, then "WEBP".
const webp = [0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x45, 0x42, 0x50];

void main() {
  test('accepts JPEG, PNG and WebP, and sends standard padded base64', () {
    for (final header in [jpeg, png, webp]) {
      final crop = Crop.fromBytes(bytes(header));
      expect(base64.decode(crop.base64), header);
    }
    expect(Crop.fromBase64('/9j/4AAQSkZJRgABAQ==').bytes.take(3), [
      0xFF,
      0xD8,
      0xFF,
    ]);
  });

  test('refuses other formats, which the server refuses (415/422)', () {
    final gif = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61];
    expect(() => Crop.fromBytes(bytes(gif)), throwsArgumentError);
    expect(() => Crop.fromBytes(Uint8List(0)), throwsArgumentError);
  });

  test('refuses a crop over the server limit of 1,000,000 bytes (413)', () {
    expect(Crop.fromBytes(bytes(jpeg, maxCropBytes)).bytes, hasLength(1000000));
    expect(
      () => Crop.fromBytes(bytes(jpeg, maxCropBytes + 1)),
      throwsArgumentError,
    );
  });

  test('refuses base64 the server would not decode (422)', () {
    // Wrong length or padding, URL-safe characters, whitespace, empty.
    for (final text in ['/9j/4A', '/9j/4AA', '/9j/4AAQS', 'AB=', 'A==', '']) {
      expect(() => Crop.fromBase64(text), throwsArgumentError, reason: text);
    }
    for (final text in ['_9j_4AAQ', '/9j/ 4AAQ', '/9j/4AAQ\n']) {
      expect(() => Crop.fromBase64(text), throwsArgumentError, reason: text);
    }
  });

  test('crops with the same bytes are equal', () {
    expect(Crop.fromBytes(bytes(jpeg)), Crop.fromBytes(bytes(jpeg)));
    expect(Crop.fromBytes(bytes(jpeg)), isNot(Crop.fromBytes(bytes(png))));
  });
}
