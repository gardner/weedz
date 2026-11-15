import 'dart:io';
import 'dart:isolate';

import 'package:cryptography/cryptography.dart';
import 'package:weedz/models/bundle_fields.dart';

/// An owned snapshot. Keep its directory while a native session uses it.
/// App code must never write this path or replace a live snapshot.
final class VerifiedModelArtifact {
  const new _(this.path, this.sha256, this.size);
  final String path;
  final String sha256;
  final int size;
}

/// Internal artifact installation; provenance is established by BundleVerifier.
/// Only paths and small metadata cross the isolate boundary, never model bytes.
Future<VerifiedModelArtifact> stageModelArtifact({
  required String sourcePath,
  required String artifactDirectory,
  required String sha256,
  required int size,
  required int maximumBytes,
}) {
  if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(sha256) ||
      size <= 0 ||
      size > maximumBytes) {
    throw const BundleRejected('Unsupported model digest or size');
  }
  return Isolate.run(
    () => _install(sourcePath, artifactDirectory, sha256, size),
    debugName: 'weedz-model-verification',
  );
}

Future<VerifiedModelArtifact> _install(
  String sourcePath,
  String artifactDirectory,
  String digest,
  int expectedSize,
) async {
  if (FileSystemEntity.typeSync(sourcePath, followLinks: false) !=
      FileSystemEntityType.file) {
    throw const BundleRejected('Model source must be a regular file');
  }
  final source = File(sourcePath);
  if (await source.length() != expectedSize) {
    throw const BundleRejected('Model length mismatch');
  }
  final root = await Directory(artifactDirectory).create(recursive: true);
  // A fresh owned directory for every invocation avoids trusting or replacing
  // any existing digest-named path, including concurrently used snapshots.
  final owned = await root.createTemp('bundle-');
  var published = false;
  try {
    final staged = File('${owned.path}/model.part');
    final output = await staged.open(mode: FileMode.writeOnly);
    final hash = Sha256().newHashSink();
    var count = 0;
    try {
      // Read at most one excess byte, even if a source grows during the copy.
      await for (final chunk in source.openRead(0, expectedSize + 1)) {
        count += chunk.length;
        if (count > expectedSize) {
          throw const BundleRejected('Model exceeds its signed size');
        }
        hash.add(chunk);
        await output.writeFrom(chunk);
      }
      hash.close();
      final actual = (await hash.hash()).bytes
          .map((v) => v.toRadixString(16).padLeft(2, '0'))
          .join();
      if (count != expectedSize || actual != digest) {
        throw const BundleRejected('Model length or SHA-256 mismatch');
      }
      await output.flush();
    } finally {
      await output.close();
    }
    final installed = await staged.rename('${owned.path}/$digest.onnx');
    published = true;
    return VerifiedModelArtifact._(
      installed.absolute.path,
      digest,
      expectedSize,
    );
  } finally {
    if (!published) await owned.delete(recursive: true);
  }
}
