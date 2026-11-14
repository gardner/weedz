/// The cropped image a report may carry, checked against the intake's limits
/// (`src/weedz/intake/limits.py` and `images.py`, issue #57).
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:meta/meta.dart';

/// The largest crop the server accepts, in decoded bytes.
const maxCropBytes = 1000000;

// Whole four-character groups with correct padding, as Python's
// `base64.b64decode(validate=True)` requires.
final _paddedBase64 = RegExp(
  r'^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$',
);

bool _startsWith(Uint8List data, List<int> prefix, [int offset = 0]) {
  if (data.length < offset + prefix.length) return false;
  for (var i = 0; i < prefix.length; i++) {
    if (data[offset + i] != prefix[i]) return false;
  }
  return true;
}

/// Whether the bytes start like one of the formats the server accepts.
bool _acceptedFormat(Uint8List data) =>
    _startsWith(data, const [0xFF, 0xD8, 0xFF]) || // JPEG
    _startsWith(data, const [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) ||
    (_startsWith(data, ascii.encode('RIFF')) &&
        _startsWith(data, ascii.encode('WEBP'), 8));

/// A JPEG, PNG or WebP crop of at most [maxCropBytes]. Its pixel size is set
/// by whatever makes the crop (a screening window, far below the server's
/// 4096 × 4096 limit), so it is not decoded here.
@immutable
final class Crop {
  new fromBytes(Uint8List data) : _bytes = Uint8List.fromList(data) {
    if (_bytes.isEmpty || _bytes.length > maxCropBytes) {
      throw ArgumentError.value(
        _bytes.length,
        'crop',
        'Must be 1 to $maxCropBytes bytes',
      );
    }
    if (!_acceptedFormat(_bytes)) {
      throw ArgumentError.value('<crop>', 'crop', 'Not JPEG, PNG or WebP');
    }
  }

  factory fromBase64(String text) {
    if (text.isEmpty || !_paddedBase64.hasMatch(text)) {
      throw ArgumentError.value('<crop>', 'crop', 'Not standard base64');
    }
    return Crop.fromBytes(base64Decode(text));
  }

  // A private copy: changing the list passed in does not change the crop.
  final Uint8List _bytes;

  /// The image bytes, read-only.
  Uint8List get bytes => _bytes.asUnmodifiableView();

  /// Standard, padded base64, as the report's `image` field.
  String get base64 => base64Encode(_bytes);

  @override
  bool operator ==(Object other) =>
      other is Crop &&
      other._bytes.length == _bytes.length &&
      _startsWith(other._bytes, _bytes);

  @override
  int get hashCode =>
      Object.hash(_bytes.length, Object.hashAll(_bytes.take(64)));
}
