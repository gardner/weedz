import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';

/// How a status looks and reads: an icon and words, never colour alone.
typedef _Look = ({IconData icon, String title, String detail, _Tone tone});

enum _Tone { neutral, good, warning, problem }

_Look _lookOf(ApprovalStatus status) => switch (status) {
  ApprovalStatus.pending => (
    icon: Icons.hourglass_empty,
    title: 'Waiting for your decision',
    detail: 'Nothing is sent until you approve this report.',
    tone: _Tone.neutral,
  ),
  ApprovalStatus.approved => (
    icon: Icons.check_circle_outline,
    title: 'Approved: ready to send',
    detail: 'Changing anything below will undo your approval.',
    tone: _Tone.good,
  ),
  ApprovalStatus.sending => (
    icon: Icons.upload,
    title: 'Sending…',
    detail: 'This report can no longer be changed.',
    tone: _Tone.neutral,
  ),
  ApprovalStatus.unanswered => (
    icon: Icons.cloud_off,
    title: 'No answer from the server',
    detail:
        'The server may already have it. You can send it again unchanged, '
        'or withdraw it.',
    tone: _Tone.warning,
  ),
  ApprovalStatus.refused => (
    icon: Icons.error_outline,
    title: 'The server refused this report',
    detail:
        'It was too big or not in the expected form. It will never be sent '
        'again as it is. You can revise it as a new report, or decline it.',
    tone: _Tone.problem,
  ),
  ApprovalStatus.received => (
    icon: Icons.cloud_done,
    title: 'Sent: the server has this report',
    detail: 'You can withdraw it at any time.',
    tone: _Tone.good,
  ),
  ApprovalStatus.withdrawn => (
    icon: Icons.undo,
    title: 'Withdrawn',
    detail: 'The server has deleted it, and it will not be sent again.',
    tone: _Tone.neutral,
  ),
  ApprovalStatus.declined => (
    icon: Icons.block,
    title: 'Declined: this report will not be sent',
    detail: 'This photo will not be suggested again by this model.',
    tone: _Tone.neutral,
  ),
  ApprovalStatus.revised => (
    icon: Icons.edit_note,
    title: 'Replaced by a revised report',
    detail: 'This version will never be sent.',
    tone: _Tone.neutral,
  ),
};

/// The report's status at the top of the screen. It is a live region, so a
/// screen reader announces each change of status politely.
class StatusBanner extends StatelessWidget {
  const new({required this.status, super.key});

  final ApprovalStatus status;

  @override
  Widget build(BuildContext context) {
    final look = _lookOf(status);
    final colours = Theme.of(context).colorScheme;
    final (background, foreground) = switch (look.tone) {
      _Tone.neutral => (colours.surfaceContainerHighest, colours.onSurface),
      _Tone.good => (colours.primaryContainer, colours.onPrimaryContainer),
      _Tone.warning => (colours.tertiaryContainer, colours.onTertiaryContainer),
      _Tone.problem => (colours.errorContainer, colours.onErrorContainer),
    };
    final text = Theme.of(context).textTheme;
    final showSpinner =
        status == ApprovalStatus.sending &&
        !MediaQuery.disableAnimationsOf(context);
    return Semantics(
      key: const Key('approval-status'),
      container: true,
      liveRegion: true,
      label: look.title,
      child: Card.filled(
        color: background,
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(
                child: showSpinner
                    ? SizedBox.square(
                        dimension: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 3,
                          color: foreground,
                        ),
                      )
                    : Icon(look.icon, color: foreground),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ExcludeSemantics(
                      child: Text(
                        look.title,
                        style: text.titleMedium?.copyWith(color: foreground),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      look.detail,
                      style: text.bodyMedium?.copyWith(color: foreground),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
