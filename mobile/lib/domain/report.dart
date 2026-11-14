/// The report a device sends once its person approves it: version 1 of the
/// server's contract (`src/weedz/intake/schema.py`, issue #57).
///
/// Each part refuses, when built, what the server's schema refuses on its
/// own. One check depends on the server's clock and is not repeated here: a
/// capture time more than a day ahead is refused (422).
/// [Report.withoutCapturedAt] lets such a report be revised.
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

/// Published versions of the consent text (`weedz.consent.VERSIONS`,
/// `docs/report-consent.md`).
const consentVersions = {'2026-11'};

/// What a photo may be used for (`weedz.consent.PERMISSIONS`). A photo is
/// sent for review, so its uses always include `review`; the rest are
/// separate opt-ins, all off by default (#60).
const photoUses = {'review', 'evidence', 'agencies', 'public', 'training'};

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

/// What the person agreed to on the device, under which published wording
/// (`docs/report-consent.md`, #60).
@immutable
final class Consent {
  new({
    required this.wordingVersion,
    required this.image,
    this.location = false,
    Set<String> uses = const {},
    this.licence,
    String? credit,
  }) : uses = Set.unmodifiable(uses),
       credit = credit?.trim() {
    _check(
      consentVersions.contains(wordingVersion),
      'wordingVersion',
      wordingVersion,
      'Not a published consent wording',
    );
    _check(
      photoUses.containsAll(uses),
      'uses',
      uses,
      'Not a photo use the consent text offers',
    );
    _check(
      image ? uses.contains('review') : uses.isEmpty,
      'uses',
      uses,
      'A photo is sent for review; a report without one permits no photo use',
    );
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

  /// Whether the person saw the exact point being sent (a map pin and its
  /// accuracy) and agreed to share it (#91). It is never blurred.
  final bool location;

  /// What the photo may be used for: empty exactly when there is no photo.
  final Set<String> uses;

  /// The crop's licence: present exactly when [image] is true.
  final String? licence;
  final String? credit;

  Consent withoutImage() => Consent(
    wordingVersion: wordingVersion,
    image: false,
    location: location,
    credit: credit,
  );

  /// This consent with location consent given or taken back.
  Consent copyWith({bool? location}) => Consent(
    wordingVersion: wordingVersion,
    image: image,
    location: location ?? this.location,
    uses: uses,
    licence: licence,
    credit: credit,
  );

  Map<String, Object?> toJson() => {
    'wording_version': wordingVersion,
    'image': image,
    'location': location,
    'uses': _sortedUses,
    'licence': ?licence,
    'credit': ?credit,
  };

  @override
  bool operator ==(Object other) =>
      other is Consent &&
      other.wordingVersion == wordingVersion &&
      other.image == image &&
      other.location == location &&
      _sameUses(other.uses, uses) &&
      other.licence == licence &&
      other.credit == credit;

  @override
  int get hashCode => Object.hash(
    wordingVersion,
    image,
    location,
    Object.hashAllUnordered(uses),
    licence,
    credit,
  );

  List<String> get _sortedUses => uses.toList()..sort();

  static bool _sameUses(Set<String> a, Set<String> b) =>
      a.length == b.length && a.containsAll(b);
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
  }) : appVersion = _checkToken(appVersion, 'appVersion') {
    _check(
      (image != null) == consent.image,
      'image',
      '<crop>',
      'An image is sent only with image consent, and consent needs one',
    );
    _check(
      (location != null) == consent.location,
      'location',
      '<location>',
      'A location is sent only with location consent, and consent needs one',
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
    consent: consent.copyWith(location: false),
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
