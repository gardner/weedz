import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:weedz/inference/margin_scoring.dart';
import 'package:weedz/inference/window_geometry.dart';
import 'package:weedz/models/bundle_fields.dart';
import 'package:weedz/models/ranking_contract.dart';

export 'package:weedz/models/bundle_fields.dart' show BundleRejected;

const _payloadType = 'application/vnd.weedz.bundle+json; version=1';
const _revisions = {
  'bioclip': 'ce901ab3c6a913f9e9ef94ce6d27761069f4f01c',
  'bioclip-2': '2957b322090f9cb17ae72c71981c7218a28d81e0',
};

class ImageRuntime {
  const new _(this.format, this.precision, this.inputDtype);
  final String format;
  final String precision;
  final String inputDtype;
}

/// Constructed after signature, delivery, artifact and contract checks.
/// This establishes provenance/conformance, not native execution or phone parity.
final class VerifiedBundle {
  new _({
    required this.sequence,
    required this.expires,
    required this.modelKey,
    required this.modelRevision,
    required this.runtime,
    required this.preprocessing,
    required this.imageModelBytes,
    required this.textRows,
    required this.targetTaxa,
  });
  final int sequence;
  final DateTime expires;
  final String modelKey;
  final String modelRevision;
  final ImageRuntime runtime;
  final Map<String, Object?> preprocessing;
  final Uint8List imageModelBytes;
  final List<List<double>> textRows;
  final List<String> targetTaxa;
  int get rankingRevision => 4;

  /// Call immediately before each inference, including cached/offline reuse.
  void ensureUsable(DateTime now) {
    final utc = now.toUtc();
    if (DateTime.utc(utc.year, utc.month, utc.day).isAfter(expires)) {
      throw const BundleRejected('Expired bundle');
    }
  }
}

class BundleVerifier {
  new({required List<String> trustedPublicKeys})
    : _pins = List<String>.unmodifiable(trustedPublicKeys);
  final List<String> _pins;

  /// All inputs are copied before the first await, preventing caller mutation.
  Future<VerifiedBundle> verify({
    required Uint8List envelopeBytes,
    required Uint8List imageModelBytes,
    required Uint8List textTableBytes,
    required int installedSequence,
    required String appVersion,
    required DateTime now,
  }) async {
    if (envelopeBytes.length > 1024 * 1024) {
      throw const BundleRejected('Manifest exceeds 1 MiB');
    }
    final model = Uint8List.fromList(imageModelBytes).asUnmodifiableView();
    final table = Uint8List.fromList(textTableBytes).asUnmodifiableView();
    try {
      final envelope = object(jsonDecode(utf8.decode(envelopeBytes)));
      final payload = await _verifiedPayload(envelope);
      final manifest = object(jsonDecode(utf8.decode(payload)));
      if (integer(manifest['schema']) != 1) {
        throw const BundleRejected('Unknown schema');
      }
      final sequence = integer(manifest['sequence'], minimum: 1);
      if (installedSequence < 0 || sequence <= installedSequence) {
        throw const BundleRejected('Replayed bundle');
      }
      final expiry = _date(text(manifest['expires']));
      final utc = now.toUtc();
      if (DateTime.utc(utc.year, utc.month, utc.day).isAfter(expiry)) {
        throw const BundleRejected('Expired bundle');
      }
      if (_version(appVersion) < _version(text(manifest['min_app_version']))) {
        throw const BundleRejected('App version is too old');
      }
      final tower = object(manifest['image_model']);
      final entry = object(manifest['text_table']);
      await _artifact(tower, model);
      await _artifact(entry, table);
      final key = text(tower['model_key']);
      final revision = text(tower['model_revision']);
      if (_revisions[key] != revision ||
          entry['model_key'] != key ||
          entry['model_revision'] != revision) {
        throw const BundleRejected('Unsupported or inconsistent model');
      }
      final runtime = _runtime(object(tower['runtime']));
      final parity = text(tower['parity']);
      if (!RegExp(r'^[a-z0-9][a-z0-9._-]{0,39}/thresholds-1$')
          .hasMatch(parity)) {
        throw const BundleRejected('Unsupported parity admission');
      }
      final screen = object(manifest['screening']);
      if (screen['model_key'] != key ||
          screen['revision'] != revision ||
          screen['ranking_revision'] != 4) {
        throw const BundleRejected('Inconsistent screening stamp');
      }
      _geometry(object(manifest['windows']));
      final taxa = array(manifest['watchlist'])
          .map((item) => text(object(item)['taxon']))
          .toList();
      _targets(manifest, entry, taxa);
      _scoring(object(manifest['scoring']), taxa);
      final rows = _table(entry, table, taxa.length);
      if (taxa.toSet().length != taxa.length) {
        throw const BundleRejected('Duplicate targets');
      }
      final preprocessing = object(tower['preprocessing']);
      _preprocessing(preprocessing);
      return VerifiedBundle._(
        sequence: sequence,
        expires: expiry,
        modelKey: key,
        modelRevision: revision,
        runtime: runtime,
        preprocessing: frozen(preprocessing)! as Map<String, Object?>,
        imageModelBytes: model,
        textRows: rows,
        targetTaxa: List.unmodifiable(taxa),
      );
    } on BundleRejected {
      rethrow;
    } on FormatException {
      throw const BundleRejected('Malformed encoding');
    }
  }

  Future<Uint8List> _verifiedPayload(Map<String, Object?> envelope) async {
    if (envelope['payloadType'] != _payloadType || _pins.isEmpty) {
      throw const BundleRejected('Unexpected type or no trusted keys');
    }
    final payload = base64Decode(text(envelope['payload']));
    final signatures = array(envelope['signatures']);
    if (signatures.length > 16) {
      throw const BundleRejected('Too many signatures');
    }
    final kind = utf8.encode(_payloadType);
    final message = [
      ...utf8.encode('DSSEv1 ${kind.length} $_payloadType ${payload.length} '),
      ...payload,
    ];
    for (final pin in _pins) {
      final raw = base64Decode(pin);
      if (raw.length != 32) throw const BundleRejected('Invalid pinned key');
      final id = _hex((await Sha256().hash(raw)).bytes).substring(0, 16);
      for (final item in signatures) {
        final signature = object(item);
        if (signature['keyid'] != id) continue;
        final bytes = base64Decode(text(signature['sig']));
        if (bytes.length == 64 &&
            await Ed25519().verify(
              message,
              signature: Signature(
                bytes,
                publicKey: SimplePublicKey(raw, type: KeyPairType.ed25519),
              ),
            )) {
          return payload;
        }
      }
    }
    throw const BundleRejected('No valid pinned signature');
  }
}

Future<void> _artifact(Map<String, Object?> entry, Uint8List bytes) async {
  if (integer(entry['size'], minimum: 1) != bytes.length ||
      text(entry['sha256']) != _hex((await Sha256().hash(bytes)).bytes)) {
    throw const BundleRejected('Artifact length or SHA-256 mismatch');
  }
}

DateTime _date(String value) {
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    throw const BundleRejected('Invalid expiry');
  }
  final date = DateTime.parse('${value}T00:00:00Z');
  if (date.toIso8601String().substring(0, 10) != value) {
    throw const BundleRejected('Invalid expiry');
  }
  return date;
}

int _version(String value) {
  if (!RegExp(r'^\d{1,4}\.\d{1,4}\.\d{1,4}$').hasMatch(value)) {
    throw const BundleRejected('Invalid version');
  }
  return value
      .split('.')
      .map(int.parse)
      .fold(0, (result, part) => result * 10000 + part);
}

ImageRuntime _runtime(Map<String, Object?> runtime) {
  final format = text(runtime['format']);
  final precision = text(runtime['precision']);
  final dtype = text(runtime['input_dtype']);
  if (format != 'onnx' ||
      !['fp32', 'fp16', 'int8'].contains(precision) ||
      !['float32', 'float16'].contains(dtype)) {
    throw const BundleRejected('Unsupported runtime');
  }
  return ImageRuntime._(format, precision, dtype);
}

List<List<double>> _table(
  Map<String, Object?> entry,
  Uint8List bytes,
  int targets,
) {
  final shape = array(entry['shape']);
  if (shape.length != 2) throw const BundleRejected('Invalid shape');
  final rows = integer(shape[0], minimum: 1);
  final width = integer(shape[1], minimum: 1);
  if (entry['dtype'] != 'float32-le' ||
      entry['normalised'] != true ||
      rows * width * 4 != bytes.length ||
      array(entry['prompts']).length != rows ||
      integer(entry['target_count'], minimum: 1) != targets ||
      targets >= rows) {
    throw const BundleRejected('Inconsistent table');
  }
  final data = ByteData.sublistView(bytes);
  return List.unmodifiable(
    List.generate(rows, (row) {
      final values = List.generate(
        width,
        (col) => data.getFloat32((row * width + col) * 4, Endian.little),
      );
      final norm = math.sqrt(
        values.fold<double>(0, (sum, value) => sum + value * value),
      );
      if (values.any((value) => !value.isFinite) || (norm - 1).abs() > 1e-5) {
        throw const BundleRejected('Text rows must be finite unit vectors');
      }
      return List<double>.unmodifiable(values);
    }),
  );
}

void _geometry(Map<String, Object?> windows) {
  if (windows['ranking_revision'] != 4 ||
      windows['tile_percent_of_short_side'] != 60 ||
      windows['max_stride_percent_of_tile'] != 75 ||
      windows['max_tiles'] != 32 ||
      windows['featureless_greyscale_std_below'] != 8 ||
      jsonEncode(windows['letterbox_rgb']) != '[124,116,104]') {
    throw const BundleRejected('Unsupported window contract');
  }
  final examples = array(windows['examples']);
  if (examples.isEmpty) throw const BundleRejected('Missing geometry vectors');
  for (final item in examples) {
    final example = object(item);
    final width = integer(example['width'], minimum: 1);
    final height = integer(example['height'], minimum: 1);
    if (width > 100000 || height > 100000) {
      throw const BundleRejected('Unsupported geometry dimensions');
    }
    final boxes = regionBoxes(width, height);
    if (jsonEncode(boxes.map(boxEdges).toList()) !=
        jsonEncode(example['boxes'])) {
      throw const BundleRejected('Geometry conformance failed');
    }
  }
}

void _preprocessing(Map<String, Object?> config) {
  if (config['mode'] != 'RGB' ||
      config['interpolation'] != 'bicubic' ||
      config['resize_mode'] != 'shortest' ||
      config['fill_color'] != 0) {
    throw const BundleRejected('Unsupported preprocessing');
  }
  final size = array(config['size']);
  if (size.length != 2 || size.any((v) => v is! int || v <= 0 || v > 4096)) {
    throw const BundleRejected('Unsupported input size');
  }
  for (final name in ['mean', 'std']) {
    final values = array(config[name]);
    if (values.length != 3) throw const BundleRejected('Invalid normalization');
    for (final value in values) {
      final number = double.parse(text(value));
      if (!number.isFinite || (name == 'std' && number <= 0)) {
        throw const BundleRejected('Invalid normalization');
      }
    }
  }
}

String _hex(List<int> bytes) =>
    bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();

void _targets(
  Map<String, Object?> manifest,
  Map<String, Object?> entry,
  List<String> taxa,
) {
  const targets = ['Clematis vitalba', 'Cortaderia selloana', 'Ulex europaeus'];
  if (jsonEncode(taxa) != jsonEncode(targets)) {
    throw const BundleRejected('Unsupported target order');
  }
  if (jsonEncode(manifest['comparisons']) != jsonEncode(ranking4Comparisons)) {
    throw const BundleRejected('Unsupported comparison label order');
  }
  final labels = [
    "Clematis vitalba, Old man's beard",
    'Cortaderia selloana, Pampas grass',
    'Ulex europaeus, Gorse',
    ...ranking4Comparisons,
  ];
  if (labels.length <= targets.length ||
      jsonEncode(entry['prompts']) !=
          jsonEncode(
            labels.map((label) => 'a photograph of $label').toList(),
          )) {
    throw const BundleRejected('Prompts do not match the table label order');
  }
}

void _scoring(Map<String, Object?> scoring, List<String> taxa) {
  if (scoring['ranking_revision'] != 4 || array(scoring['examples']).isEmpty) {
    throw const BundleRejected('Unsupported scoring contract');
  }
  for (final item in array(scoring['examples'])) {
    final example = object(item);
    final similarities = array(example['similarities'])
        .map(
          (row) =>
              array(row)
                  .map((v) => integer(v, minimum: -9007199254740991).toDouble())
                  .toList(),
        )
        .toList();
    final excluded = array(example['featureless_windows']).map(integer).toSet();
    if (similarities.isEmpty ||
        similarities.any(
          (r) =>
              r.length <= taxa.length || r.length != similarities.first.length,
        ) ||
        excluded.contains(0) ||
        excluded.any((i) => i >= similarities.length)) {
      throw const BundleRejected('Invalid scoring vector');
    }
    final result = summarizeMargins(
      similarities: similarities,
      targetTaxa: taxa,
      eligible: List.generate(
        similarities.length,
        (i) => !excluded.contains(i),
      ),
    );
    final margins = object(example['margins']);
    if (result.best.taxon != example['best_species'] ||
        margins.length != taxa.length ||
        result.targets.any(
          (target) => margins[target.taxon] != target.margin,
        )) {
      throw const BundleRejected('Scoring conformance failed');
    }
  }
}
