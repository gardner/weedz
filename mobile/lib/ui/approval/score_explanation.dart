/// What a report's score means, in plain words, keyed by the declared score
/// meaning it was screened under (#16, `src/weedz/discovery/score_meaning.py`).
///
/// A copy of the server's declarations for the models the app can run. A
/// declaration is never edited, so a new one is added here under its own id.
/// A report screened under an id not listed here is told plainly that its
/// score has no declared meaning.
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';

/// Common names for the declared target taxa.
const commonNames = {
  'Clematis vitalba': "old man's beard",
  'Cortaderia selloana': 'pampas grass',
  'Ulex europaeus': 'gorse',
};

@immutable
final class ScoreExplanation {
  const new({required this.points, this.meaningId});

  /// The declared meaning's id, or null when none is declared.
  final String? meaningId;

  /// Plain sentences, read in order.
  final List<String> points;
}

const _whatItIs =
    'The score compares how much the photo looks like this weed with how '
    'much it looks like native lookalikes and other things in the same '
    'place. Higher means the weed matched more strongly.';

const _notProbability =
    'It is not a probability, and not a confidence that the weed is there.';

const _noCutOff =
    'A positive score does not mean the weed is present. No cut-off has been '
    'chosen yet.';

const _undeclared =
    'No meaning has been declared for this model’s scores, so the score '
    'cannot be read on its own. Treat the suggestion as unchecked.';

const List<String> _notMeaning = [_notProbability, _noCutOff];

/// The lookalike evidence behind each declared meaning: how many native or
/// lookalike photos had the weed they resemble as the top suggestion.
const _lookalikeTop = {
  'bioclip-2/ranking-4/meaning-1': (30, 39),
  'bioclip/ranking-4/meaning-1': (32, 39),
};

ScoreExplanation explainScore(Screening model) {
  final id = model.scoreMeaning;
  final lookalikes = _lookalikeTop[id];
  if (id == null || lookalikes == null) {
    return const ScoreExplanation(points: [_undeclared, ..._notMeaning]);
  }
  final (count, of) = lookalikes;
  final lookalikeEvidence =
      'Native plants can score as a weed: in testing, $count of $of '
      'lookalike photos had the weed they resemble as the top suggestion.';
  return ScoreExplanation(
    meaningId: id,
    points: [_whatItIs, ..._notMeaning, lookalikeEvidence],
  );
}
