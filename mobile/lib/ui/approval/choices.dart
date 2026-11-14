/// What the person chooses to share, before the choices become a report.
///
/// The domain [Consent] is a plain yes or no, so it cannot say "not answered
/// yet". [Choices] can: each answer starts null, and approval waits until
/// every needed answer is given. Nothing is chosen for the person.
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
  const new({this.crop, this.location});

  final Crop? crop;
  final Location? location;
}

/// The person's answers. Null means not answered yet.
@immutable
final class Choices {
  const new({this.sendPhoto, this.licence, this.shareLocation});

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

  /// [report] with these answers applied, through the domain's own edits.
  /// Only an explicit yes puts a photo or a location in.
  Report applyTo(Report report, Findings found) {
    final place = found.location;
    var next = place != null && (shareLocation ?? false)
        ? report.copyWith(location: place)
        : report.withoutLocation();
    final crop = found.crop;
    final licence_ = licence;
    if (crop != null && (sendPhoto ?? false) && licence_ != null) {
      final consent = next.consent;
      next = next.copyWith(
        image: crop,
        consent: Consent(
          wordingVersion: consent.wordingVersion,
          image: true,
          licence: licence_,
          credit: consent.credit,
        ),
      );
    } else {
      next = next.withoutImage();
    }
    return next;
  }
}
