/// The buttons for what can happen next to a report, by status. Final
/// actions (decline, withdraw) ask first, in a dialog screen readers can use.
library;

import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/domain/report.dart';

/// What each action does; the store commits the transition (#57). Decline
/// and withdraw receive the case the person was asked about, which may be
/// out of date by the time they confirm.
typedef ActionHandlers = ({
  VoidCallback approve,
  VoidCallback send,
  ValueChanged<ReportCase> decline,
  ValueChanged<ReportCase> withdraw,
  void Function(Report Function(Report) change) revise,
});

class ApprovalActions extends StatelessWidget {
  const new({
    required this.reportCase,
    required this.choicesComplete,
    required this.handlers,
    super.key,
  });

  final ReportCase reportCase;

  /// Whether the person has answered every choice the report needs.
  final bool choicesComplete;
  final ActionHandlers handlers;

  @override
  Widget build(BuildContext context) {
    final report = reportCase.report;
    final buttons = switch (reportCase.status) {
      ApprovalStatus.pending => [
        _gate(
          FilledButton(
            onPressed: choicesComplete ? handlers.approve : null,
            child: const Text('Approve this report'),
          ),
          'approve',
        ),
        _decline(context),
      ],
      ApprovalStatus.approved => [
        _gate(
          FilledButton(
            onPressed: choicesComplete ? handlers.send : null,
            child: const Text('Send report'),
          ),
          'send',
        ),
        _decline(context),
      ],
      ApprovalStatus.sending || ApprovalStatus.received => [_withdraw(context)],
      ApprovalStatus.unanswered => [
        FilledButton(
          onPressed: handlers.send,
          child: const Text('Send again unchanged'),
        ),
        _withdraw(context),
      ],
      ApprovalStatus.refused => [
        if (report.image != null)
          OutlinedButton(
            onPressed: () => handlers.revise((r) => r.withoutImage()),
            child: const Text('Revise without the photo'),
          ),
        if (report.capturedAt != null)
          OutlinedButton(
            onPressed: () => handlers.revise((r) => r.withoutCapturedAt()),
            child: const Text('Revise without the capture time'),
          ),
        _decline(context),
      ],
      ApprovalStatus.declined ||
      ApprovalStatus.revised ||
      ApprovalStatus.withdrawn => <Widget>[],
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final button in buttons)
          Padding(padding: const EdgeInsets.only(top: 12), child: button),
      ],
    );
  }

  /// [button], with the reason it is disabled in plain view, not hidden in
  /// a tooltip.
  Widget _gate(Widget button, String verb) => choicesComplete
      ? button
      : Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Answer every choice above to $verb.'),
            const SizedBox(height: 8),
            button,
          ],
        );

  Widget _decline(BuildContext context) => OutlinedButton(
    onPressed: () => _confirm(
      context,
      title: 'Decline this report?',
      body:
          'It will never be sent, and this model will not suggest this photo '
          'again.',
      keep: 'Keep deciding',
      act: 'Decline report',
      then: () => handlers.decline(reportCase),
    ),
    child: const Text('Decline'),
  );

  Widget _withdraw(BuildContext context) => OutlinedButton(
    onPressed: () => _confirm(
      context,
      title: 'Withdraw this report?',
      body:
          'The server will delete the report and its photo, and it will not '
          'be used again. Anything already shared before you withdraw cannot '
          'be recalled.',
      keep: 'Keep it',
      act: 'Withdraw',
      then: () => handlers.withdraw(reportCase),
    ),
    child: const Text('Withdraw report'),
  );

  static Future<void> _confirm(
    BuildContext context, {
    required String title,
    required String body,
    required String keep,
    required String act,
    required VoidCallback then,
  }) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(keep),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(act),
          ),
        ],
      ),
    );
    if (confirmed ?? false) then();
  }
}
