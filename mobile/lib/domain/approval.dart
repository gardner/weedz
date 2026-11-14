/// The life of one found report, from the scan to the server (#56, #57).
///
/// The rule it enforces: nothing is sent unless the person approved exactly
/// this report. Any edit undoes approval, and only an approved report yields
/// an [Upload].
library;

import 'package:meta/meta.dart';
import 'package:weedz/domain/report.dart';

enum ApprovalStatus {
  /// Found by the scan, waiting for the person.
  pending,

  /// The person said no. Final: it is never sent.
  declined,

  /// The person approved this exact report; it may be sent.
  approved,

  /// Being sent. Frozen until the server answers.
  sending,

  /// The server has it and returned a receipt.
  received,

  /// Withdrawn from the server.
  withdrawn,
}

final _uuid = RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
);

/// What goes over the wire: `PUT /reports/{id}` with [body] as JSON.
@immutable
final class Upload {
  const new _(this.id, this.body);

  final String id;
  final Map<String, Object?> body;
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
  bool get maySend =>
      status == ApprovalStatus.approved || status == ApprovalStatus.sending;

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
    {ApprovalStatus.pending, ApprovalStatus.approved},
    ApprovalStatus.declined,
    'decline',
  );

  ReportCase startSending() =>
      _move({ApprovalStatus.approved}, ApprovalStatus.sending, 'send');

  /// The send did not get an answer: still approved, to retry under [id].
  ReportCase sendFailed() =>
      _move({ApprovalStatus.sending}, ApprovalStatus.approved, 'fail');

  ReportCase received() =>
      _move({ApprovalStatus.sending}, ApprovalStatus.received, 'receive');

  /// Withdrawn by the person, or found withdrawn on the server (410).
  ReportCase withdrawn() => _move(
    {ApprovalStatus.sending, ApprovalStatus.received},
    ApprovalStatus.withdrawn,
    'withdraw',
  );

  /// The request to send, available only while approved.
  Upload upload() {
    _expect({ApprovalStatus.approved}, 'upload');
    return Upload._(id, report.toJson());
  }

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
