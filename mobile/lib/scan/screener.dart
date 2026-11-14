/// The on-device model, as the scan sees it: an image in, scores out.
///
/// The real one runs BioCLIP 2's image tower through Core ML or LiteRT (#51).
/// Until then only test fakes implement it.
library;

import 'package:weedz/scan/library.dart';

/// The best margin per weed (taxon name to margin, in [-2, 2]) over the
/// image's windows, as in the revision 4 ranking.
typedef Margins = Map<String, double>;

abstract interface class Screener {
  /// Which model and ranking produced the scores. A new revision means every
  /// photo is screened again.
  String get modelRevision;

  Future<Margins> screen(ScanImage image);
}
