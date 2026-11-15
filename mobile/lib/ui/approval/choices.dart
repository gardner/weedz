/// What the person chooses to share, before the choices become a report.
///
/// New reports omit the photo and include a recorded location when available.
/// An optional photo still requires its own explicitly chosen licence.
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';

/// The licences offered for a photo, in the order shown, with their plain
/// meaning. CC BY-NC comes first as the suggestion (#60), but none is
/// preselected.
const licenceLabels = {
  'cc-by-nc': 'CC BY-NC 4.0: credit me, no commercial use',
  'cc-by': 'CC BY 4.0: credit me',
  'cc0': 'CC0: no rights reserved',
};

/// What the scan found for a report, kept beside it, so a removed photo or
/// location can be put back. Either may be missing: a photo may have no
/// location with a known accuracy (#54).
@immutable
final class Findings {
  const new({this.crop, this.location, this.credit});

  final Crop? crop;
  final Location? location;

  /// Locally retained attribution supplied by the person.
  /// Sent only with a crop.
  final String? credit;
}

/// The visible sharing choices. Null is accepted for older absent findings.
@immutable
final class Choices {
  const new({this.sendPhoto = false, this.licence, this.shareLocation = true});

  /// The answers a report already records, for a report the person has
  /// decided on (approved, sent, or revised from their earlier answers).
  new fromReport(Report report, Findings found)
    : sendPhoto = found.crop == null ? null : report.image != null,
      licence = report.consent.licence,
      shareLocation = found.location == null ? null : report.location != null;

  final bool? sendPhoto;
  final String? licence;
  final bool? shareLocation;

  Choices withPhoto({required bool send}) =>
      Choices(sendPhoto: send, licence: licence, shareLocation: shareLocation);

  Choices withLicence(String chosen) => Choices(
    sendPhoto: sendPhoto,
    licence: chosen,
    shareLocation: shareLocation,
  );

  Choices withLocation({required bool share}) =>
      Choices(sendPhoto: sendPhoto, licence: licence, shareLocation: share);

  /// Whether every answer [found] needs has been given. Nothing to choose
  /// means nothing to answer.
  bool isCompleteFor(Findings found) {
    final photoAnswered =
        found.crop == null ||
        sendPhoto == false ||
        (sendPhoto ?? false) && licence != null;
    final locationAnswered = found.location == null || shareLocation != null;
    return photoAnswered && locationAnswered;
  }

  /// [report] with these answers applied, checked by the domain's [Report].
  /// The report action approves these visible choices together.
  Report applyTo(Report report, Findings found) {
    final place = (shareLocation ?? false) ? found.location : null;
    final licence_ = licence;
    final crop = (sendPhoto ?? false) && licence_ != null ? found.crop : null;
    // Each part goes with its consent (#60, #91); the domain refuses either
    // without the other.
    return Report(
      appVersion: report.appVersion,
      candidate: report.candidate,
      model: report.model,
      capturedAt: report.capturedAt,
      location: place,
      image: crop,
      consent: Consent(
        wordingVersion: currentConsentVersion,
        image: crop != null,
        location: place != null,
        // A photo is sent for review. The other uses (`evidence`, `agencies`,
        // `public`, `training`) are opt-ins this screen does not offer yet, so
        // none is given (docs/report-consent.md).
        uses: crop == null ? const {} : const {'review'},
        licence: crop == null ? null : licence_,
        credit: crop == null ? null : found.credit,
      ),
    );
  }
}
