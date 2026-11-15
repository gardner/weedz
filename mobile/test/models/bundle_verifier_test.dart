import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/models/bundle_verifier.dart';

const folder = 'test/fixtures/model_bundle';

Future<VerifiedBundle> verify({
  Uint8List? envelope,
  Uint8List? model,
  Uint8List? table,
  int installed = 0,
  String version = '0.1.0',
  DateTime? now,
  List<String>? pins,
}) =>
    BundleVerifier(
      trustedPublicKeys:
          pins ?? [File('$folder/public-key.txt').readAsStringSync().trim()],
    ).verify(
      envelopeBytes:
          envelope ?? File('$folder/envelope.json').readAsBytesSync(),
      imageModelBytes: model ?? File('$folder/model.onnx').readAsBytesSync(),
      textTableBytes: table ?? File('$folder/text.f32').readAsBytesSync(),
      installedSequence: installed,
      appVersion: version,
      now: now ?? DateTime.utc(2026, 11, 15),
    );

Future<Uint8List> edited(
  FutureOr<void> Function(Map<String, dynamic>) edit,
) async {
  final envelope = jsonDecode(
    File('$folder/envelope.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final payload = jsonDecode(
    utf8.decode(base64Decode(envelope['payload'] as String)),
  ) as Map<String, dynamic>;
  await edit(payload);
  final bytes = utf8.encode(jsonEncode(payload));
  final message = [
    ...utf8.encode(
      'DSSEv1 44 application/vnd.weedz.bundle+json; version=1 ${bytes.length} ',
    ),
    ...bytes,
  ];
  // Public, deterministic fixture key. Never configured by the application.
  final algorithm = Ed25519();
  final key = await algorithm.newKeyPairFromSeed(List.generate(32, (i) => i));
  final signature = await algorithm.sign(message, keyPair: key);
  envelope['payload'] = base64Encode(bytes);
  final first = (envelope['signatures'] as List).first as Map<String, dynamic>;
  first['sig'] = base64Encode(signature.bytes);
  return Uint8List.fromList(utf8.encode(jsonEncode(envelope)));
}

void main() {
  test(
    'accepts Python DSSE bytes and exposes immutable verified artifacts',
    () async {
      final bundle = await verify();
      expect(bundle.sequence, 7);
      expect(bundle.modelKey, 'bioclip-2');
      expect(bundle.runtime.format, 'onnx');
      expect(bundle.textRows.first, [0.5, 0.5, 0.5, 0.5]);
      expect(bundle.targetTaxa.length, 3);
      expect(() => bundle.imageModelBytes[0] = 0, throwsUnsupportedError);
      expect(() => bundle.textRows.first[0] = 0, throwsUnsupportedError);
    },
  );

  test(
    'empty pins, altered signed bytes and corrupt artifacts fail closed',
    () async {
      await expectLater(verify(pins: []), throwsA(isA<BundleRejected>()));
      final envelope = File('$folder/envelope.json')
          .readAsStringSync()
          .replaceFirst('DSSE', 'BAD');
      final json = jsonDecode(envelope) as Map<String, dynamic>;
      json['payload'] = base64Encode(utf8.encode('{}'));
      await expectLater(
        verify(envelope: Uint8List.fromList(utf8.encode(jsonEncode(json)))),
        throwsA(isA<BundleRejected>()),
      );
      await expectLater(
        verify(model: Uint8List(1)),
        throwsA(isA<BundleRejected>()),
      );
      final table = File('$folder/text.f32').readAsBytesSync()..[0] ^= 1;
      await expectLater(verify(table: table), throwsA(isA<BundleRejected>()));
    },
  );

  test('delivery checks reject replay, expiry and newer minimum app', () async {
    await expectLater(verify(installed: 7), throwsA(isA<BundleRejected>()));
    await expectLater(
      verify(now: DateTime.utc(2027, 2, 15)),
      throwsA(isA<BundleRejected>()),
    );
    await expectLater(verify(version: '0.0.9'), throwsA(isA<BundleRejected>()));
    expect((await verify(now: DateTime.utc(2027, 2, 14, 23, 59))).sequence, 7);
  });

  test(
    'validly signed unsupported or inconsistent contracts are refused',
    () async {
      final edits = <void Function(Map<String, dynamic>)>[
        (m) => m['schema'] = 2,
        (m) => (m['scoring'] as Map)['ranking_revision'] = 99,
        (m) => (m['scoring'] as Map)['examples'] = <Object?>[],
        (m) => (m['text_table'] as Map)['prompts'] = List.filled(16, 'wrong'),
        (m) => (m['watchlist'] as List).removeLast(),
        (m) => m['sequence'] = 7.5,
        (m) => m['expires'] = '2027-02-30',
        (m) => (m['image_model'] as Map)['parity'] = 'onnx-fp16/thresholds-99',
        (m) =>
            ((m['image_model'] as Map)['runtime'] as Map)['format'] = 'unknown',
        (m) => (m['windows'] as Map)['tile_percent_of_short_side'] = 80,
        (m) => (m['text_table'] as Map)['shape'] = [16, 0],
        (m) => (m['text_table'] as Map)['model_revision'] = 'other',
        (m) => (m['text_table'] as Map)['normalised'] = false,
      ];
      for (final edit in edits) {
        await expectLater(
          verify(envelope: await edited(edit)),
          throwsA(isA<BundleRejected>()),
        );
      }
    },
  );
  test('cached capability expires on the day after signed expiry', () async {
    final bundle = await verify();
    bundle.ensureUsable(DateTime.utc(2027, 2, 14, 23, 59));
    expect(
      () => bundle.ensureUsable(DateTime.utc(2027, 2, 15)),
      throwsA(isA<BundleRejected>()),
    );
  });

  test(
    'verified table rejects signed nonfinite or unnormalized rows',
    () async {
      for (final value in [double.nan, double.infinity, 0.0, 2.0]) {
        final table = File('$folder/text.f32').readAsBytesSync();
        ByteData.sublistView(table).setFloat32(0, value, Endian.little);
        final digest = (await Sha256().hash(table)).bytes
            .map((v) => v.toRadixString(16).padLeft(2, '0'))
            .join();
        final envelope = await edited(
          (m) => (m['text_table'] as Map)['sha256'] = digest,
        );
        await expectLater(
          verify(envelope: envelope, table: table),
          throwsA(isA<BundleRejected>()),
        );
      }
    },
  );

  test(
    'caller changes during asynchronous verification cannot change artifacts',
    () async {
      final model = File('$folder/model.onnx').readAsBytesSync();
      final original = List<int>.of(model);
      final future = verify(model: model);
      model.fillRange(0, model.length, 0);
      expect((await future).imageModelBytes, original);
    },
  );
  test(
    'comparison changes cannot redefine ranking 4 even with matching rows',
    () async {
      for (final change in ['replace', 'reorder', 'add', 'remove']) {
        late Uint8List table;
        final envelope = await edited((m) async {
          final comparisons = List<String>.from(m['comparisons'] as List);
          if (change == 'replace') comparisons[0] = 'a new comparison';
          if (change == 'reorder') {
            final first = comparisons[0];
            comparisons[0] = comparisons[1];
            comparisons[1] = first;
          }
          if (change == 'add') comparisons.add('another comparison');
          if (change == 'remove') comparisons.removeLast();
          m['comparisons'] = comparisons;
          final entry = m['text_table'] as Map;
          final targetPrompts = (entry['prompts'] as List).take(3).toList();
          entry['prompts'] = [
            ...targetPrompts,
            ...comparisons.map((v) => 'a photograph of $v'),
          ];
          final rows = 3 + comparisons.length;
          table = Uint8List(rows * 4 * 4);
          final bytes = ByteData.sublistView(table);
          for (var i = 0; i < rows * 4; i++) {
            bytes.setFloat32(i * 4, 0.5, Endian.little);
          }
          entry['shape'] = [rows, 4];
          entry['size'] = table.length;
          entry['sha256'] = (await Sha256().hash(table)).bytes
              .map((v) => v.toRadixString(16).padLeft(2, '0'))
              .join();
        });
        await expectLater(
          verify(envelope: envelope, table: table),
          throwsA(isA<BundleRejected>()),
          reason: change,
        );
      }
    },
  );
}
