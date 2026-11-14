/// One report, on its own screen, for the person to approve, decline, send,
/// revise or withdraw (#56). Built accessibly from the start (#63).
///
/// The rules live in the domain ([ReportCase]); this screen only shows the
/// case and asks it for transitions, which go out through callbacks for the
/// store to commit. What it shows is `reportCase.report`, the value that
/// will be serialised, so what is shown is what is sent.
library;

import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/approval.dart';
import 'package:weedz/domain/report.dart';
import 'package:weedz/ui/approval/approval_actions.dart';
import 'package:weedz/ui/approval/choices.dart';
import 'package:weedz/ui/approval/report_id.dart';
import 'package:weedz/ui/approval/report_sections.dart';
import 'package:weedz/ui/approval/status_banner.dart';

export 'package:weedz/ui/approval/choices.dart' show Findings, licenceLabels;

class ApprovalScreen extends StatefulWidget {
  const new({
    required this.reportCase,
    required this.findings,
    required this.onChanged,
    required this.onSend,
    required this.onWithdraw,
    required this.onRevised,
    this.newId = newReportId,
    super.key,
  });

  final ReportCase reportCase;

  /// What the scan found, so a removed photo or location can be put back.
  final Findings findings;

  /// An edit, an approval or a decline, to commit.
  final ValueChanged<ReportCase> onChanged;

  /// An approved (or unanswered) case to freeze and send with
  /// [ReportCase.startSending].
  final ValueChanged<ReportCase> onSend;

  /// A sent case to withdraw with `DELETE`.
  final ValueChanged<ReportCase> onWithdraw;

  /// A refused case retired, and its revision as a new case: save both
  /// together.
  final void Function(ReportCase retired, ReportCase revision) onRevised;

  /// Makes the id for a revision.
  final String Function() newId;

  @override
  State<ApprovalScreen> createState() => _ApprovalScreenState();
}

class _ApprovalScreenState extends State<ApprovalScreen> {
  late Choices _choices = _startingChoices();

  /// The choices to carry over to a revision this screen just made.
  Choices? _carried;

  ReportCase get _case => widget.reportCase;

  bool get _editable =>
      _case.status == ApprovalStatus.pending ||
      _case.status == ApprovalStatus.approved;

  /// A report waiting for a decision starts with nothing chosen. One already
  /// decided on shows the answers it records.
  Choices _startingChoices() => _case.status == ApprovalStatus.pending
      ? const Choices()
      : Choices.fromReport(_case.report, widget.findings);

  @override
  void didUpdateWidget(ApprovalScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.reportCase.id != widget.reportCase.id) {
      _choices = _carried ?? _startingChoices();
      _carried = null;
    }
  }

  Report _applied() => _choices.applyTo(_case.report, widget.findings);

  /// Records an answer. Once every answer is given, the report is edited to
  /// match, which undoes any approval.
  void _choose(Choices next) {
    setState(() => _choices = next);
    if (!next.isCompleteFor(widget.findings)) return;
    final edited = _case.edit(_applied());
    if (!identical(edited, _case)) widget.onChanged(edited);
  }

  void _approve() => widget.onChanged(_case.edit(_applied()).approve());

  void _revise(Report Function(Report) change) {
    final (retired, revision) = _case.revise(
      id: widget.newId(),
      report: change(_case.report),
    );
    _carried = Choices.fromReport(revision.report, widget.findings);
    widget.onRevised(retired, revision);
  }

  /// Whether the report is still as it was when the person was asked to
  /// confirm: a send can finish, or be refused, while a dialog is open.
  bool _isStill(ReportCase asked) =>
      asked.id == _case.id && asked.status == _case.status;

  @override
  Widget build(BuildContext context) {
    final report = _case.report;
    final choose = _editable ? _choose : null;
    return Scaffold(
      appBar: AppBar(title: const Text('Review this report')),
      body: SafeArea(
        // A short page, so it is built whole: every part is in the
        // semantics tree, for screen readers to reach.
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              StatusBanner(status: _case.status),
              SuggestionSection(report: report),
              PhotoSection(
                report: report,
                findings: widget.findings,
                choices: _choices,
                onChoose: choose,
              ),
              LocationSection(
                report: report,
                findings: widget.findings,
                choices: _choices,
                onChoose: choose,
              ),
              const SizedBox(height: 16),
              if (report.consent.credit case final credit?)
                Text('Your credit name, sent with this report: $credit.'),
              Text(
                'Consent wording ${report.consent.wordingVersion}.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              ApprovalActions(
                reportCase: _case,
                choicesComplete: _choices.isCompleteFor(widget.findings),
                handlers: (
                  approve: _approve,
                  send: () => widget.onSend(_case),
                  decline: (asked) {
                    if (_isStill(asked)) widget.onChanged(_case.decline());
                  },
                  withdraw: (asked) {
                    if (_isStill(asked)) widget.onWithdraw(_case);
                  },
                  revise: _revise,
                ),
              ),
              const SizedBox(key: Key('approval-end'), height: 1),
            ],
          ),
        ),
      ),
    );
  }
}
