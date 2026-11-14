/// The life of one found report, from the scan to the server (#56, #57).
///
/// The rule it enforces: nothing is sent unless the person approved exactly
/// this report. Any edit undoes approval, and an [Upload] exists only for a
/// report frozen for sending in the same step, as immutable JSON text.
library;

import 'dart:convert';

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';

enum ApprovalStatus {
  /// Found by the scan, waiting for the person.
  pending,

  /// The person said no. Final: it is never sent.
  declined,

  /// The person approved this exact report; it may be sent.
  approved,

  /// Being sent. Frozen from here on: the id now stands for this content.
  sending,

  /// Sent without an answer, so the server may have it. It can only be sent
  /// again, unchanged under the same id, or withdrawn.
  unanswered,

  /// The server refused it as sent (413, 415 or 422). It is never sent again
  /// under this id: the person can decline it, or revise it as a new case.
  refused,

  /// A refused report replaced by a new case under a new id. Final.
  revised,

  /// The server has it and returned a receipt.
  received,

  /// Withdrawn: not on the server, and never sent again.
  withdrawn,
}

final _uuid = RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
);

/// What goes over the wire: `PUT /reports/{id}` with [body].
@immutable
final class Upload {
  const new _(this.id, this.body);

  final String id;

  /// The approved report as JSON text: a String, so nothing can change it
  /// between approval and sending.
  final String body;
}

@immutable
final class ReportCase {
  /// A report the scan found, under a random UUID the device chose. The id is
  /// kept across retries, so the server sees a retry as the same report.
  new found({required this.id, required this.report})
    : status = ApprovalStatus.pending {
    if (!_uuid.hasMatch(id)) {
      throw ArgumentError.value(id, 'id', 'Not a lower-case UUID');
    }
  }

  const new _(this.id, this.report, this.status);

  final String id;
  final Report report;
  final ApprovalStatus status;

  /// Whether this report may be on its way to the server.
  bool get maySend => const {
    ApprovalStatus.approved,
    ApprovalStatus.sending,
    ApprovalStatus.unanswered,
  }.contains(status);

  /// Replaces the report. A change needs approving again; an unchanged
  /// report keeps its status.
  ReportCase edit(Report updated) {
    _expect({ApprovalStatus.pending, ApprovalStatus.approved}, 'edit');
    if (updated == report) return this;
    return ReportCase._(id, updated, ApprovalStatus.pending);
  }

  ReportCase approve() =>
      _move({ApprovalStatus.pending}, ApprovalStatus.approved, 'approve');

  ReportCase decline() => _move(
    {ApprovalStatus.pending, ApprovalStatus.approved, ApprovalStatus.refused},
    ApprovalStatus.declined,
    'decline',
  );

  /// Freezes the approved report for sending (or sends an unanswered one
  /// again) and returns the request to send. Both happen in one step, so no
  /// [Upload] exists for a report that can still be edited or declined.
  (ReportCase, Upload) startSending() {
    final sending = _move(
      {ApprovalStatus.approved, ApprovalStatus.unanswered},
      ApprovalStatus.sending,
      'send',
    );
    return (sending, Upload._(id, jsonEncode(report.toJson())));
  }

  /// The send got no answer. The report stays frozen, since the server may
  /// have stored it under [id].
  ReportCase sendFailed() =>
      _move({ApprovalStatus.sending}, ApprovalStatus.unanswered, 'fail');

  ReportCase refused() =>
      _move({ApprovalStatus.sending}, ApprovalStatus.refused, 'refuse');

  /// A refused report, changed, as a new pending case under a new [id], so
  /// the refused id never stands for different content and the refused
  /// content is never sent again. The refused case is retired in the same
  /// step, so it cannot be revised twice; save both together.
  (ReportCase, ReportCase) revise({
    required String id,
    required Report report,
  }) {
    final retired = _move(
      {ApprovalStatus.refused},
      ApprovalStatus.revised,
      'revise',
    );
    if (id == this.id) {
      throw ArgumentError.value(id, 'id', 'A revision needs a new id');
    }
    if (report == this.report) {
      throw ArgumentError.value(
        '<report>',
        'report',
        'A revision must change it',
      );
    }
    return (retired, ReportCase.found(id: id, report: report));
  }

  ReportCase received() =>
      _move({ApprovalStatus.sending}, ApprovalStatus.received, 'receive');

  /// Confirmed withdrawn: a receipt from `DELETE`, or a 410. An older server
  /// may return 404 without recording intent. That is not confirmation while
  /// a `PUT` may still be in flight: repeat `DELETE` once the `PUT` settles.
  ReportCase withdrawn() => _move(
    {
      ApprovalStatus.sending,
      ApprovalStatus.unanswered,
      ApprovalStatus.received,
    },
    ApprovalStatus.withdrawn,
    'withdraw',
  );

  ReportCase _move(Set<ApprovalStatus> from, ApprovalStatus to, String verb) {
    _expect(from, verb);
    return ReportCase._(id, report, to);
  }

  void _expect(Set<ApprovalStatus> allowed, String verb) {
    if (!allowed.contains(status)) {
      throw StateError('Cannot $verb a ${status.name} report');
    }
  }
}
