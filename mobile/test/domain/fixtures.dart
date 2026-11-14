import 'dart:io';

import 'package:weedz/domain/report.dart';

/// A fixture file's text, from `test/fixtures` (tests run from the package root).
String fixtureJson(String name) =>
    File('test/fixtures/$name').readAsStringSync();

/// The start of a JPEG (the fixture's crop), enough for the header checks.
Crop jpegCrop() => Crop.fromBase64('/9j/4AAQSkZJRgABAQ==');

Consent imageConsent() => Consent(
  wordingVersion: 'consent-2026-11',
  image: true,
  licence: 'cc-by',
  credit: 'A. Contributor',
);

/// Every field filled, matching `test/fixtures/report_v1.json`.
Report fullReport() => Report(
  appVersion: '0.1.0+1',
  candidate: Candidate(taxon: 'Clematis vitalba', score: 0.051),
  model: Screening(
    modelKey: 'bioclip-2',
    revision: '2957b322090f9cb17ae72c71981c7218a28d81e0',
    rankingRevision: 4,
    scoreMeaning: 'bioclip-2/ranking-4/meaning-1',
  ),
  capturedAt: DateTime.utc(2026, 10, 2, 23, 15, 42),
  location: Location(
    latitude: -41.2706319,
    longitude: 173.2839653,
    accuracyM: 4.7,
  ),
  consent: imageConsent(),
  image: jpegCrop(),
);

/// Only the required fields.
Report minimalReport() => Report(
  appVersion: '0.1.0+1',
  candidate: Candidate(taxon: 'Ulex europaeus', score: -0.004),
  model: Screening(
    modelKey: 'bioclip-2',
    revision: '2957b322090f9cb17ae72c71981c7218a28d81e0',
    rankingRevision: 4,
  ),
  consent: Consent(wordingVersion: 'consent-2026-11', image: false),
);
