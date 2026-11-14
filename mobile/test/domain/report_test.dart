import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/report.dart';

import 'fixtures.dart';

void main() {
  group('Report JSON (contract v1, #57)', () {
    test('matches the fixture the server contract test checks', () {
      final fixture = jsonDecode(fixtureJson('report_v1.json'));
      expect(fullReport().toJson(), fixture);
    });

    test('leaves out absent optional fields instead of sending nulls', () {
      final json = minimalReport().toJson();
      expect(json.containsKey('captured_at'), isFalse);
      expect(json.containsKey('location'), isFalse);
      expect(json.containsKey('image'), isFalse);
      expect((json['model']! as Map).containsKey('score_meaning'), isFalse);
      expect((json['consent']! as Map).containsKey('licence'), isFalse);
      expect((json['consent']! as Map).containsKey('credit'), isFalse);
    });

    test('sends the capture time in UTC with its zone', () {
      final local = DateTime.utc(2026, 3, 4, 5, 6, 7).toLocal();
      final json = minimalReport().copyWith(capturedAt: local).toJson();
      expect(json['captured_at'], '2026-03-04T05:06:07.000Z');
    });

    test('keeps exact coordinates and their accuracy', () {
      final location = fullReport().toJson()['location']! as Map;
      expect(location['latitude'], -41.2706319);
      expect(location['longitude'], 173.2839653);
      expect(location['accuracy_m'], 4.7);
    });
  });

  group('Report refuses what the server would refuse', () {
    test('an exact location requires its own explicit consent', () {
      expect(
        () => minimalReport().copyWith(location: fullReport().location),
        throwsArgumentError,
      );
      expect(
        () => minimalReport().copyWith(
          consent: Consent(
            wordingVersion: '2026-11',
            image: false,
            location: true,
          ),
        ),
        throwsArgumentError,
      );
    });

    test('a taxon outside the declared targets', () {
      expect(
        () => Candidate(taxon: 'Bellis perennis', score: 0.1),
        throwsArgumentError,
      );
    });

    test('a score outside [-2, 2] or not finite', () {
      for (final score in [2.01, -2.01, double.nan, double.infinity]) {
        expect(
          () => Candidate(taxon: 'Ulex europaeus', score: score),
          throwsArgumentError,
          reason: '$score',
        );
      }
    });

    test('coordinates out of range, or accuracy that is not positive', () {
      expect(
        () => Location(latitude: 90.1, longitude: 0, accuracyM: 5),
        throwsArgumentError,
      );
      expect(
        () => Location(latitude: 0, longitude: -180.1, accuracyM: 5),
        throwsArgumentError,
      );
      expect(
        () => Location(latitude: 0, longitude: 0, accuracyM: 0),
        throwsArgumentError,
      );
      expect(
        () => Location(latitude: 0, longitude: 0, accuracyM: 100001),
        throwsArgumentError,
      );
    });

    test('a token that does not match the server pattern', () {
      expect(
        () =>
            Screening(modelKey: 'has space', revision: 'r', rankingRevision: 4),
        throwsArgumentError,
      );
      expect(
        () => Screening(modelKey: 'm', revision: 'r', rankingRevision: 0),
        throwsArgumentError,
      );
    });

    test('a licence without image consent, or image consent without one', () {
      expect(
        () => Consent(
          wordingVersion: '2026-11',
          image: false,
          location: false,
          licence: 'cc0',
        ),
        throwsArgumentError,
      );
      expect(
        () => Consent(wordingVersion: '2026-11', location: false, image: true),
        throwsArgumentError,
      );
    });

    test('a licence the collection does not admit', () {
      expect(
        () => Consent(
          wordingVersion: '2026-11',
          location: false,
          image: true,
          licence: 'cc-by-sa',
        ),
        throwsArgumentError,
      );
    });

    test('a blank or overlong credit, and trims the rest', () {
      expect(
        () => Consent(
          wordingVersion: '2026-11',
          image: false,
          location: false,
          credit: '   ',
        ),
        throwsArgumentError,
      );
      expect(
        () => Consent(
          wordingVersion: '2026-11',
          image: false,
          location: false,
          credit: 'x' * 81,
        ),
        throwsArgumentError,
      );
      final consent = Consent(
        wordingVersion: '2026-11',
        image: false,
        location: false,
        credit: ' A ',
      );
      expect(consent.credit, 'A');
    });

    test('an image without image consent, and image consent without one', () {
      expect(
        () => minimalReport().copyWith(image: jpegCrop()),
        throwsArgumentError,
      );
      expect(
        () => minimalReport().copyWith(consent: imageConsent(location: false)),
        throwsArgumentError,
      );
    });

    test('an unpublished consent wording', () {
      expect(
        () => Consent(
          wordingVersion: 'consent-2099-01',
          image: false,
          location: false,
        ),
        throwsArgumentError,
      );
    });

    test('photo uses need review, are known, and need a photo', () {
      Consent photo(Set<String> uses) => Consent(
        wordingVersion: '2026-11',
        image: true,
        location: false,
        uses: uses,
        licence: 'cc-by-nc',
      );
      expect(() => photo({'training'}), throwsArgumentError);
      expect(() => photo({'review', 'advertising'}), throwsArgumentError);
      expect(
        () => Consent(
          wordingVersion: '2026-11',
          image: false,
          location: false,
          uses: const {'review'},
        ),
        throwsArgumentError,
      );
      expect(photo({'training', 'review'}).toJson()['uses'], [
        'review',
        'training',
      ]);
    });
  });

  group('Removing details before approval (#56)', () {
    test('withoutLocation drops the location and nothing else', () {
      final report = fullReport().withoutLocation();
      expect(report.location, isNull);
      expect(report.consent.location, isFalse);
      expect(report.image, fullReport().image);
      expect(report.consent.image, fullReport().consent.image);
    });

    test('withoutCapturedAt drops the capture time and nothing else', () {
      // So a report the server refuses for a wrong camera clock can be revised.
      final report = fullReport().withoutCapturedAt();
      expect(report.capturedAt, isNull);
      expect(report.location, fullReport().location);
      expect(report.consent.location, isTrue);
      expect(report.image, fullReport().image);
    });

    test('withoutImage drops the crop, its consent and its licence', () {
      final report = fullReport().withoutImage();
      expect(report.image, isNull);
      expect(report.consent.image, isFalse);
      expect(report.consent.licence, isNull);
      expect(report.consent.location, isTrue);
      expect(report.consent.credit, fullReport().consent.credit);
      expect(report.consent.uses, isEmpty);
      expect(report.location, fullReport().location);
    });
  });

  test('reports with the same content are equal', () {
    expect(fullReport(), fullReport());
    expect(fullReport().hashCode, fullReport().hashCode);
    expect(fullReport(), isNot(fullReport().withoutLocation()));
  });
}
