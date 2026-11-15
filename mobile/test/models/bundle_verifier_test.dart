import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/models/bundle_verifier.dart';

const folder = 'test/fixtures/model_bundle';
late Directory artifactDirectory;

Future<VerifiedBundle> verify({
  Uint8List? envelope,
  Uint8List? model,
  File? modelFile,
  int maxModelBytes = 2 * 1024 * 1024 * 1024,
  Uint8List? table,
  int installed = 0,
  String version = '0.1.0',
  DateTime? now,
  List<String>? pins,
}) async {
  var source = modelFile ?? File('$folder/model.onnx');
  if (model != null) {
    source = await File('${artifactDirectory.path}/download')
        .writeAsBytes(model);
  }
  return await BundleVerifier(
    trustedPublicKeys:
        pins ?? [File('$folder/public-key.txt').readAsStringSync().trim()],
    artifactDirectory: artifactDirectory,
    maxModelBytes: maxModelBytes,
  ).verify(
    envelopeBytes: envelope ?? File('$folder/envelope.json').readAsBytesSync(),
    imageModelFile: source,
    textTableBytes: table ?? File('$folder/text.f32').readAsBytesSync(),
    installedSequence: installed,
    appVersion: version,
    now: now ?? DateTime.utc(2026, 11, 15),
  );
}

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
  setUp(() async {
    artifactDirectory = await Directory.systemTemp.createTemp(
      'weedz-bundle-test-',
    );
  });
  tearDown(() async {
    await artifactDirectory.delete(recursive: true);
  });
  test(
    'accepts Python DSSE bytes and exposes immutable verified artifacts',
    () async {
      final bundle = await verify();
      expect(bundle.sequence, 7);
      expect(bundle.modelKey, 'bioclip-2');
      expect(bundle.runtime.format, 'onnx');
      expect(bundle.textRows.first, [0.5, 0.5, 0.5, 0.5]);
      expect(bundle.targetTaxa.length, 3);
      expect(
        bundle.imageModel.path,
        isNot(File('$folder/model.onnx').absolute.path),
      );
      expect(bundle.imageModel.sha256, hasLength(64));
      expect(
        await File(bundle.imageModel.path).length(),
        bundle.imageModel.size,
      );
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

  test('source replacement cannot alter the verifier-owned artifact', () async {
    final original = File('$folder/model.onnx').readAsBytesSync();
    final source = await File('${artifactDirectory.path}/source.onnx')
        .writeAsBytes(original);
    final bundle = await verify(modelFile: source);
    await source.delete();
    await source.writeAsBytes(List.filled(original.length, 0));
    expect(await File(bundle.imageModel.path).readAsBytes(), original);
  });

  test(
    'size limits and corrupt sources leave no owned staging directories',
    () async {
      await expectLater(
        verify(maxModelBytes: 1),
        throwsA(isA<BundleRejected>()),
      );
      await expectLater(
        verify(model: Uint8List(1)),
        throwsA(isA<BundleRejected>()),
      );
      final directories = await artifactDirectory
          .list()
          .where((v) => v is Directory)
          .toList();
      expect(directories, isEmpty);
    },
  );

  test('existing digest names are never trusted or overwritten', () async {
    final first = await verify();
    final original = await File(first.imageModel.path).readAsBytes();
    final plant = File(
      '${artifactDirectory.path}/${first.imageModel.sha256}.onnx',
    );
    await plant.writeAsString('corrupt existing file');
    final next = await verify();
    expect(next.imageModel.path, isNot(first.imageModel.path));
    expect(await File(first.imageModel.path).readAsBytes(), original);
    expect(await File(next.imageModel.path).readAsBytes(), original);
    expect(await plant.readAsString(), 'corrupt existing file');
  });

  test(
    'large artifacts stream off the UI isolate into an owned snapshot',
    () async {
      final source = File('${artifactDirectory.path}/large-source.onnx');
      final output = await source.open(mode: FileMode.writeOnly);
      final chunk = Uint8List.fromList(
        List.generate(64 * 1024, (i) => i % 256),
      );
      final sink = Sha256().newHashSink();
      for (var i = 0; i < 128; i++) {
        sink.add(chunk);
        await output.writeFrom(chunk);
      }
      await output.close();
      sink.close();
      final digest = (await sink.hash()).bytes
          .map((v) => v.toRadixString(16).padLeft(2, '0'))
          .join();
      final envelope = await edited((m) {
        final tower = m['image_model'] as Map;
        tower['size'] = chunk.length * 128;
        tower['sha256'] = digest;
      });
      var ticks = 0;
      final timer = Timer.periodic(
        const Duration(milliseconds: 1),
        (_) => ticks++,
      );
      late VerifiedBundle bundle;
      try {
        bundle = await verify(envelope: envelope, modelFile: source);
      } finally {
        timer.cancel();
      }
      expect(ticks, greaterThan(0));
      expect(bundle.imageModel.size, chunk.length * 128);
      expect(await File(bundle.imageModel.path).length(), chunk.length * 128);
      expect(bundle.imageModel.sha256, digest);
    },
  );

  test(
    'symlink model sources fail before any owned snapshot is created',
    () async {
      final link = Link('${artifactDirectory.path}/source-link');
      await link.create(File('$folder/model.onnx').absolute.path);
      await expectLater(
        verify(modelFile: File(link.path)),
        throwsA(isA<BundleRejected>()),
      );
      expect(
        await artifactDirectory.list().where((v) => v is Directory).toList(),
        isEmpty,
      );
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
