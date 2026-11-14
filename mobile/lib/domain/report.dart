/// The report a device sends once its person approves it: version 1 of the
/// server's contract (`src/weedz/intake/schema.py`, issue #57).
///
/// Each part refuses, when built, what the server's schema refuses on its
/// own. Capture times more than a day ahead of the device clock are refused.
/// The server checks its own clock too; [Report.withoutCapturedAt] lets a
/// report be revised if the clocks disagree.
///
/// The location is exact on purpose (it is what makes a report useful for
/// science) and always carries its accuracy. It is where
/// the camera was, not the plant.
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/crop.dart';

export 'package:weedz/domain/crop.dart' show Crop;

const schemaVersion = 1;

/// The declared target taxa (`weedz.discovery.records.SPECIES`).
const targetTaxa = {
  'Clematis vitalba',
  'Cortaderia selloana',
  'Ulex europaeus',
};

/// Image licences the collection admits (`weedz.discovery.sharing.ADMITTED`).
const admittedLicences = {'cc0', 'cc-by', 'cc-by-nc'};

/// The largest location accuracy the server accepts, in metres.
const maxAccuracyM = 100000.0;

final _token = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$');
final _meaningId = RegExp(r'^[a-z0-9][a-z0-9./-]{0,119}$');

void _check(bool ok, String name, Object? value, String rule) {
  if (!ok) throw ArgumentError.value(value, name, rule);
}

String _checkToken(String value, String name) {
  _check(_token.hasMatch(value), name, value, 'Not a token');
  return value;
}

double _checkRange(double value, String name, double min, double max) {
  _check(
    value.isFinite && value >= min && value <= max,
    name,
    value,
    'Must be within [$min, $max]',
  );
  return value;
}

/// The suggested weed: a suggestion to be checked, not an identification.
@immutable
final class Candidate {
  new({required this.taxon, required double score})
    // A margin between two cosine similarities, so it lies in [-2, 2].
    : score = _checkRange(score, 'score', -2, 2) {
    _check(
      targetTaxa.contains(taxon),
      'taxon',
      taxon,
      'Not a declared target taxon',
    );
  }

  final String taxon;
  final double score;

  Map<String, Object?> toJson() => {'taxon': taxon, 'score': score};

  @override
  bool operator ==(Object other) =>
      other is Candidate && other.taxon == taxon && other.score == score;

  @override
  int get hashCode => Object.hash(taxon, score);
}

/// What produced the score, so it is compared only with like scores (#16).
@immutable
final class Screening {
  new({
    required String modelKey,
    required String revision,
    required this.rankingRevision,
    this.scoreMeaning,
  }) : modelKey = _checkToken(modelKey, 'modelKey'),
       revision = _checkToken(revision, 'revision') {
    _check(
      rankingRevision >= 1 && rankingRevision <= 10000,
      'rankingRevision',
      rankingRevision,
      'Must be within [1, 10000]',
    );
    final meaning = scoreMeaning;
    _check(
      meaning == null || _meaningId.hasMatch(meaning),
      'scoreMeaning',
      meaning,
      'Not a score-meaning id',
    );
  }

  final String modelKey;
  final String revision;
  final int rankingRevision;

  /// Null when the configuration has no declared score meaning.
  final String? scoreMeaning;

  Map<String, Object?> toJson() => {
    'model_key': modelKey,
    'revision': revision,
    'ranking_revision': rankingRevision,
    'score_meaning': ?scoreMeaning,
  };

  @override
  bool operator ==(Object other) =>
      other is Screening &&
      other.modelKey == modelKey &&
      other.revision == revision &&
      other.rankingRevision == rankingRevision &&
      other.scoreMeaning == scoreMeaning;

  @override
  int get hashCode =>
      Object.hash(modelKey, revision, rankingRevision, scoreMeaning);
}

/// Where the camera was, exactly, with how far off that may be.
@immutable
final class Location {
  new({
    required double latitude,
    required double longitude,
    required double accuracyM,
  }) : latitude = _checkRange(latitude, 'latitude', -90, 90),
       longitude = _checkRange(longitude, 'longitude', -180, 180),
       accuracyM = _checkRange(accuracyM, 'accuracyM', 0, maxAccuracyM) {
    _check(accuracyM > 0, 'accuracyM', accuracyM, 'Must be positive');
  }

  final double latitude;
  final double longitude;

  /// The radius in metres the true position lies within.
  final double accuracyM;

  Map<String, Object?> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
    'accuracy_m': accuracyM,
  };

  @override
  bool operator ==(Object other) =>
      other is Location &&
      other.latitude == latitude &&
      other.longitude == longitude &&
      other.accuracyM == accuracyM;

  @override
  int get hashCode => Object.hash(latitude, longitude, accuracyM);
}

/// What the person agreed to on the device, under which wording.
@immutable
final class Consent {
  new({
    required String wordingVersion,
    required this.image,
    this.licence,
    String? credit,
  }) : wordingVersion = _checkToken(wordingVersion, 'wordingVersion'),
       credit = credit?.trim() {
    final licence_ = licence;
    _check(
      licence_ == null || admittedLicences.contains(licence_),
      'licence',
      licence_,
      'Not an admitted licence',
    );
    _check(
      image == (licence_ != null),
      'licence',
      licence_,
      'Image consent and an image licence go together',
    );
    final credit_ = this.credit;
    _check(
      credit_ == null || (credit_.isNotEmpty && credit_.length <= 80),
      'credit',
      credit,
      'Must be 1 to 80 characters',
    );
  }

  final String wordingVersion;

  /// Whether a cropped image may be sent.
  final bool image;

  /// The crop's licence: present exactly when [image] is true.
  final String? licence;
  final String? credit;

  Consent withoutImage() =>
      Consent(wordingVersion: wordingVersion, image: false, credit: credit);

  Map<String, Object?> toJson() => {
    'wording_version': wordingVersion,
    'image': image,
    'licence': ?licence,
    'credit': ?credit,
  };

  @override
  bool operator ==(Object other) =>
      other is Consent &&
      other.wordingVersion == wordingVersion &&
      other.image == image &&
      other.licence == licence &&
      other.credit == credit;

  @override
  int get hashCode => Object.hash(wordingVersion, image, licence, credit);
}

/// A report as sent. Capture time and location may be missing on the device
/// (#54); the crop is sent only with image consent.
@immutable
final class Report {
  new({
    required String appVersion,
    required this.candidate,
    required this.model,
    required this.consent,
    this.capturedAt,
    this.location,
    this.image,
    DateTime Function()? clock,
  }) : appVersion = _checkToken(appVersion, 'appVersion') {
    final captured = capturedAt;
    _check(
      captured == null ||
          !captured.isAfter(
            (clock ?? DateTime.now)().add(const Duration(days: 1)),
          ),
      'capturedAt',
      captured,
      'Must be no more than one day in the future',
    );
    _check(
      (image != null) == consent.image,
      'image',
      '<crop>',
      'An image is sent only with image consent, and consent needs one',
    );
  }

  final String appVersion;
  final Candidate candidate;
  final Screening model;
  final DateTime? capturedAt;
  final Location? location;
  final Consent consent;

  /// The crop, sent as standard base64.
  final Crop? image;

  /// This report with some parts replaced (to remove a part, use
  /// [withoutLocation] or [withoutImage]).
  Report copyWith({
    DateTime? capturedAt,
    Location? location,
    Consent? consent,
    Crop? image,
  }) => Report(
    appVersion: appVersion,
    candidate: candidate,
    model: model,
    capturedAt: capturedAt ?? this.capturedAt,
    location: location ?? this.location,
    consent: consent ?? this.consent,
    image: image ?? this.image,
  );

  Report withoutLocation() => Report(
    appVersion: appVersion,
    candidate: candidate,
    model: model,
    capturedAt: capturedAt,
    consent: consent,
    image: image,
  );

  Report withoutCapturedAt() => Report(
    appVersion: appVersion,
    candidate: candidate,
    model: model,
    location: location,
    consent: consent,
    image: image,
  );

  Report withoutImage() => Report(
    appVersion: appVersion,
    candidate: candidate,
    model: model,
    capturedAt: capturedAt,
    location: location,
    consent: consent.withoutImage(),
  );

  /// The JSON body, leaving out absent optional fields.
  Map<String, Object?> toJson() => {
    'schema_version': schemaVersion,
    'app_version': appVersion,
    'candidate': candidate.toJson(),
    'model': model.toJson(),
    'captured_at': ?capturedAt?.toUtc().toIso8601String(),
    'location': ?location?.toJson(),
    'consent': consent.toJson(),
    'image': ?image?.base64,
  };

  @override
  bool operator ==(Object other) =>
      other is Report &&
      other.appVersion == appVersion &&
      other.candidate == candidate &&
      other.model == model &&
      other.capturedAt == capturedAt &&
      other.location == location &&
      other.consent == consent &&
      other.image == image;

  @override
  int get hashCode => Object.hash(
    appVersion,
    candidate,
    model,
    capturedAt,
    location,
    consent,
    image,
  );
}
