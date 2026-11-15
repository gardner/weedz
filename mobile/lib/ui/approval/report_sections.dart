/// The parts of the approval screen that show the report: what was
/// suggested, the photo and the location, each with the person's choices
/// while the report can still change.
library;

import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/ui/approval/choices.dart';
import 'package:weedz/ui/approval/location_view.dart';
import 'package:weedz/ui/approval/score_explanation.dart';

/// A section title, marked as a heading so screen readers can jump to it.
class SectionTitle extends StatelessWidget {
  const new(this.title, {super.key});

  final String title;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 24, bottom: 8),
    child: Semantics(
      header: true,
      child: Text(title, style: Theme.of(context).textTheme.titleLarge),
    ),
  );
}

/// The suggested weed, worded as a suggestion, with what its score means.
class SuggestionSection extends StatelessWidget {
  const new({required this.report, super.key});

  final Report report;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final taxon = report.candidate.taxon;
    final explanation = explainScore(report.model);
    final capturedAt = report.capturedAt;
    final meaning = explanation.meaningId ?? 'no declared meaning';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionTitle('Suggested weed'),
        Text('$taxon (${commonNames[taxon]})', style: text.titleMedium),
        const SizedBox(height: 4),
        const Text(
          'Unchecked suggestion, not an identification. '
          'The score is not a probability.',
        ),
        Text('Model score: ${report.candidate.score}', style: text.bodyMedium),
        ExpansionTile(
          title: const Text('About this score'),
          children: [
            Text('Score meaning: $meaning'),
            for (final point in explanation.points)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(point),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          capturedAt == null
              ? 'The photo has no capture time, so none is sent.'
              // Exactly as sent (`Report.toJson`), to the millisecond.
              : 'Taken ${capturedAt.toUtc().toIso8601String()} (UTC)',
        ),
      ],
    );
  }
}

/// Two answers to one question, neither chosen until the person picks one.
class _YesNo extends StatelessWidget {
  const new({
    required this.value,
    required this.yes,
    required this.no,
    required this.onChanged,
  });

  final bool? value;
  final String yes;
  final String no;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => RadioGroup<bool>(
    groupValue: value,
    onChanged: (chosen) {
      if (chosen != null) onChanged(chosen);
    },
    child: Column(
      children: [
        RadioListTile<bool>(value: true, title: Text(yes)),
        RadioListTile<bool>(value: false, title: Text(no)),
      ],
    ),
  );
}

/// The crop, and whether and under which licence it is sent.
class PhotoSection extends StatelessWidget {
  const new({
    required this.report,
    required this.preview,
    required this.choices,
    required this.onChoose,
    this.failed = false,
    this.onPreview,
    super.key,
  });

  final bool failed;
  final ValueChanged<bool>? onPreview;
  final Report report;

  /// The crop the person may send, or null when there is none.
  final ImageProvider? preview;
  final Choices choices;

  /// Null once the report can no longer change.
  final ValueChanged<Choices>? onChoose;

  @override
  Widget build(BuildContext context) {
    final image = preview;
    final choose = onChoose;
    void previewed(bool decoded) {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => onPreview?.call(decoded),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionTitle('Photo'),
        if (image == null)
          const Text('There is no photo to send with this report.')
        else ...[
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 240),
            child: Image(
              image: image,
              semanticLabel: 'The cropped part of your photo',
              frameBuilder: (context, child, frame, synchronous) {
                if (synchronous || frame != null) previewed(true);
                return child;
              },
              errorBuilder: (context, error, stack) {
                previewed(false);
                return const Text(
                  'The photo could not be shown. It cannot be attached.',
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          if (choose == null)
            Text(_frozenSummary())
          else if (!failed)
            ExpansionTile(
              title: const Text('Attach a photo (optional)'),
              subtitle: const Text(
                'No photo is sent unless you choose to attach it.',
              ),
              initiallyExpanded: choices.sendPhoto ?? false,
              children: [
                _YesNo(
                  value: choices.sendPhoto,
                  yes: 'Send this photo',
                  no: "Don't send the photo",
                  onChanged: (send) => choose(choices.withPhoto(send: send)),
                ),
                if (choices.sendPhoto ?? false) ...[
                  const SectionTitle('Licence for the photo'),
                  const Text(
                    'Choose how others may use it. Experts always see a photo '
                    'you send, to check the report.',
                  ),
                  RadioGroup<String>(
                    groupValue: choices.licence,
                    onChanged: (licence) {
                      if (licence != null) choose(choices.withLicence(licence));
                    },
                    child: Column(
                      children: [
                        for (final MapEntry(:key, :value)
                            in licenceLabels.entries)
                          RadioListTile<String>(value: key, title: Text(value)),
                      ],
                    ),
                  ),
                ],
              ],
            ),
        ],
      ],
    );
  }

  String _frozenSummary() {
    final licence = report.consent.licence;
    if (report.image == null || licence == null) {
      return 'The photo is not sent.';
    }
    return 'The photo is sent under ${licenceLabels[licence]}.';
  }
}

/// The exact location, and whether it is shared.
class LocationSection extends StatelessWidget {
  const new({
    required this.report,
    required this.findings,
    required this.choices,
    required this.onChoose,
    super.key,
  });

  final Report report;
  final Findings findings;
  final Choices choices;

  /// Null once the report can no longer change.
  final ValueChanged<Choices>? onChoose;

  @override
  Widget build(BuildContext context) {
    final location = report.location;
    final choose = onChoose;
    final canChoose = choose != null && findings.location != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionTitle('Location'),
        if (location != null)
          LocationView(location: location)
        else if (findings.location == null)
          const Text(
            'This photo has no location with a known accuracy, so the report '
            'is sent without one.',
          )
        else
          const Text('Location removed. It will not be sent.'),
        if (canChoose) ...[
          const SizedBox(height: 8),
          const Text(
            'Exact locations are what make a report useful to science. '
            'The people who check reports see this exact point.',
          ),
          _YesNo(
            value: choices.shareLocation,
            yes: 'Share this exact location',
            no: 'Remove the location',
            onChanged: (share) => choose(choices.withLocation(share: share)),
          ),
        ],
      ],
    );
  }
}
