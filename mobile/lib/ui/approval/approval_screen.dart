/// One report, on its own screen, for the person to approve, decline, send,
/// revise or withdraw (#56). Built accessibly from the start (#63).
///
/// The rules live in the domain ([ReportCase]); this screen only shows the
/// case and asks it for transitions, which go out through callbacks for the
/// store to commit. Editable previews apply the visible choices locally;
/// Report sighting approves that exact snapshot before asking the store
/// to send.
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
  /// [ReportCase.startSending]. The persisted case may still be pending:
  /// atomically compare its id/status and commit this exact approved snapshot
  /// plus the frozen sending/outbox state. Serialize edits and send per case;
  /// reject a second send once sending. This callback must not depend on an
  /// earlier onChanged callback or parent rebuild. Catch operational failures
  /// in the caller and reconcile its persisted case/outbox: throwing has an
  /// unknown commit outcome and leaves this snapshot locked. Only a known
  /// settled status may advance it. If storage proves no commit occurred,
  /// remount a fresh screen with a new key; never reset it merely on timeout.
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
  late Findings _found = _merged();
  late Choices _choices = _startingChoices();

  /// One image provider per crop, so a rebuild does not decode it again.
  (Crop, MemoryImage)? _preview;

  /// The choices to carry over to a revision this screen just made.
  Choices? _carried;

  Crop? _decoded;
  Crop? _failed;
  ReportCase? _requested;
  bool _requestUnconfirmed = false;

  ReportCase get _case => widget.reportCase;

  bool get _editable =>
      _requested == null &&
      (_case.status == ApprovalStatus.pending ||
          _case.status == ApprovalStatus.approved);

  /// What the person may choose from: the scan's findings, or failing that
  /// what the report already holds, so nothing shown is silently dropped.
  Findings _merged({Findings? previous}) => Findings(
    crop: widget.findings.crop ?? _case.report.image,
    location: widget.findings.location ?? _case.report.location,
    credit:
        widget.findings.credit ??
        _case.report.consent.credit ??
        previous?.credit,
  );

  MemoryImage? get _photo {
    final crop = _found.crop;
    if (crop == null) return null;
    final cached = _preview;
    if (cached != null && cached.$1 == crop) return cached.$2;
    final image = MemoryImage(crop.bytes);
    _preview = (crop, image);
    return image;
  }

  /// Pending means unapproved, not untouched: reopening must preserve edits.
  /// Callers create fresh drafts without an image and with any recorded
  /// location they will visibly offer; findings only retain removable data.
  Choices _startingChoices() => Choices.fromReport(_case.report, _found);

  @override
  void didUpdateWidget(ApprovalScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final newCase = oldWidget.reportCase.id != widget.reportCase.id;
    if (newCase || !identical(oldWidget.findings, widget.findings)) {
      _found = _merged(previous: newCase ? null : _found);
    }
    // Sending and settlement may coalesce into a single parent rebuild.
    // A new immutable settled case acknowledges work even at the same status.
    if (newCase ||
        (_case.status != ApprovalStatus.pending &&
            _case.status != ApprovalStatus.approved &&
            !identical(oldWidget.reportCase, _case))) {
      _requested = null;
      _requestUnconfirmed = false;
    }
    if (newCase) {
      _choices = _carried ?? _startingChoices();
      _carried = null;
    }
  }

  Report _applied() => _choices.applyTo(_case.report, _found);

  /// Records an answer. Once every answer is given, the report is edited to
  /// match, which undoes any approval.
  void _choose(Choices next) {
    if (!_editable) return;
    setState(() => _choices = next);
    if (!next.isCompleteFor(_found)) return;
    final edited = _case.edit(_applied());
    if (!identical(edited, _case)) widget.onChanged(edited);
  }

  bool get _ready =>
      _choices.isCompleteFor(_found) &&
      (_choices.sendPhoto != true || _decoded == _found.crop);

  void _previewed(Crop crop, bool decoded) {
    if (!mounted || crop != _found.crop || !_editable) return;
    if (decoded ? _decoded == crop : _failed == crop) return;
    setState(() {
      if (decoded) {
        _decoded = crop;
      } else {
        _failed = crop;
      }
    });
    if (!decoded && _choices.sendPhoto == true) {
      _choose(_choices.withPhoto(send: false));
    }
  }

  void _send() {
    if (_requested != null) return;
    var snapshot = _case;
    if (_editable) {
      if (!_ready) return;
      snapshot = _case.edit(_applied());
      if (snapshot.status == ApprovalStatus.pending) {
        snapshot = snapshot.approve();
      }
    } else if (_case.status != ApprovalStatus.unanswered) {
      return;
    }
    setState(() => _requested = snapshot);
    try {
      widget.onSend(snapshot);
    } catch (_) {
      // The callback may have committed before throwing. Keep the frozen
      // snapshot locked until the caller reconciles storage; never guess.
      setState(() => _requestUnconfirmed = true);
      rethrow;
    }
  }

  void _revise(Report Function(Report) change) {
    final (retired, revision) = _case.revise(
      id: widget.newId(),
      report: change(_case.report),
    );
    _carried = Choices.fromReport(revision.report, _found);
    widget.onRevised(retired, revision);
  }

  /// Whether the report the person confirmed is still this one. A send can
  /// settle while a dialog is open, so each action then checks that the
  /// current status still allows it.
  bool _isSame(ReportCase asked) => _requested == null && asked.id == _case.id;

  @override
  Widget build(BuildContext context) {
    final report =
        _requested?.report ?? (_editable ? _applied() : _case.report);
    final choose = _editable ? _choose : null;
    final crop = _found.crop;
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
                preview: _photo,
                choices: _choices,
                onChoose: choose,
                failed: _failed == _found.crop && _found.crop != null,
                onPreview: crop == null
                    ? null
                    : (decoded) => _previewed(crop, decoded),
              ),
              LocationSection(
                report: report,
                findings: _found,
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
                requested: _requested != null,
                requestUnconfirmed: _requestUnconfirmed,
                choicesComplete: _ready,
                handlers: (
                  send: _send,
                  decline: (asked) {
                    if (_isSame(asked) && _case.mayDecline) {
                      widget.onChanged(_case.decline());
                    }
                  },
                  withdraw: (asked) {
                    if (_isSame(asked) && _case.mayWithdraw) {
                      widget.onWithdraw(_case);
                    }
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
