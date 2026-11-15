import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Imports that could send something off the phone.
final _network = RegExp(
  r'''^\s*(import|export)\s+['"]'''
  '(dart:io|dart:html|package:http/|package:dio/|package:web_socket|'
  'package:web/|package:grpc/)',
  multiLine: true,
);

void main() {
  test('nothing under lib/scan can reach the network', () {
    final sources = Directory('lib/scan')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .toList();
    expect(sources, isNotEmpty);
    for (final source in sources) {
      expect(
        _network.hasMatch(source.readAsStringSync()),
        isFalse,
        reason:
            '${source.path} imports networking code; scanning never '
            'uploads anything (docs/mobile.md, Privacy properties)',
      );
    }
  });
}
