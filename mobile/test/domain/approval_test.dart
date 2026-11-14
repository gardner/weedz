import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/approval.dart';

import 'fixtures.dart';

const id = '0b6f3f43-8c55-4a52-9d1e-6a1f0c7d2e11';

ReportCase found() => ReportCase.found(id: id, report: fullReport());

void main() {
  group('A found report', () {
    test('waits for the person, and may not be sent', () {
      final found_ = found();
      expect(found_.status, ApprovalStatus.pending);
      expect(found_.maySend, isFalse);
      expect(found_.upload, throwsStateError);
    });

    test('needs a lower-case UUID the device chose', () {
      expect(
        () => ReportCase.found(id: 'not-a-uuid', report: fullReport()),
        throwsArgumentError,
      );
      expect(
        () => ReportCase.found(id: id.toUpperCase(), report: fullReport()),
        throwsArgumentError,
      );
    });
  });

  group('Approving', () {
    test('lets exactly the approved report be sent, under its id', () {
      final approved = found().approve();
      expect(approved.status, ApprovalStatus.approved);
      expect(approved.maySend, isTrue);
      final upload = approved.upload();
      expect(upload.id, id);
      expect(upload.body, fullReport().toJson());
    });

    test('is undone by any edit, which needs approving again', () {
      final edited = found().approve().edit(fullReport().withoutLocation());
      expect(edited.status, ApprovalStatus.pending);
      expect(edited.maySend, isFalse);
      expect(edited.report.location, isNull);
      expect(edited.approve().upload().body.containsKey('location'), isFalse);
    });

    test('an edit that changes nothing keeps the approval', () {
      final approved = found().approve();
      expect(approved.edit(fullReport()).status, ApprovalStatus.approved);
    });
  });

  group('Declining', () {
    test('is final and never sends', () {
      for (final declined in [found().decline(), found().approve().decline()]) {
        expect(declined.status, ApprovalStatus.declined);
        expect(declined.maySend, isFalse);
        expect(declined.approve, throwsStateError);
        expect(() => declined.edit(fullReport()), throwsStateError);
      }
    });
  });

  group('Sending', () {
    test('starts only from approval', () {
      expect(found().startSending, throwsStateError);
      expect(found().approve().startSending().status, ApprovalStatus.sending);
    });

    test('a failed send stays approved, so a retry reuses the same id', () {
      final retry = found().approve().startSending().sendFailed();
      expect(retry.status, ApprovalStatus.approved);
      expect(retry.upload().id, id);
    });

    test('freezes the report: no edits or declining in flight', () {
      final sending = found().approve().startSending();
      expect(() => sending.edit(fullReport()), throwsStateError);
      expect(sending.decline, throwsStateError);
      expect(sending.maySend, isTrue);
    });

    test('ends with the receipt, after which only withdrawal remains', () {
      final received = found().approve().startSending().received();
      expect(received.status, ApprovalStatus.received);
      expect(received.maySend, isFalse);
      expect(() => received.edit(fullReport()), throwsStateError);
      expect(received.withdrawn().status, ApprovalStatus.withdrawn);
    });

    test('a report withdrawn elsewhere (410) ends withdrawn', () {
      final sending = found().approve().startSending();
      expect(sending.withdrawn().status, ApprovalStatus.withdrawn);
    });
  });

  test('withdrawal needs a report the server has or may have', () {
    expect(found().withdrawn, throwsStateError);
    expect(found().approve().withdrawn, throwsStateError);
  });
}
