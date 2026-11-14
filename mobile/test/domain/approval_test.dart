import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/domain/approval.dart';

import 'fixtures.dart';

const id = '0b6f3f43-8c55-4a52-9d1e-6a1f0c7d2e11';

ReportCase found() => ReportCase.found(id: id, report: fullReport());

ReportCase sending() => found().approve().startSending().$1;

Map<String, Object?> sent(Upload upload) =>
    jsonDecode(upload.body) as Map<String, Object?>;

void main() {
  group('A found report', () {
    test('waits for the person, and may not be sent', () {
      final found_ = found();
      expect(found_.status, ApprovalStatus.pending);
      expect(found_.maySend, isFalse);
      expect(found_.startSending, throwsStateError);
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
      final (frozen, upload) = approved.startSending();
      expect(frozen.status, ApprovalStatus.sending);
      expect(upload.id, id);
      expect(sent(upload), fullReport().toJson());
    });

    test('is undone by any edit, which needs approving again', () {
      final edited = found().approve().edit(fullReport().withoutLocation());
      expect(edited.status, ApprovalStatus.pending);
      expect(edited.maySend, isFalse);
      expect(edited.report.location, isNull);
      final (_, upload) = edited.approve().startSending();
      expect(sent(upload).containsKey('location'), isFalse);
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
        expect(declined.startSending, throwsStateError);
        expect(() => declined.edit(fullReport()), throwsStateError);
      }
    });
  });

  group('Sending', () {
    test('freezes the case in the same step that yields the upload', () {
      // There is no way to hold an Upload for a case that can still change.
      final (frozen, _) = found().approve().startSending();
      expect(() => frozen.edit(fullReport()), throwsStateError);
      expect(frozen.decline, throwsStateError);
      expect(frozen.startSending, throwsStateError);
      expect(frozen.maySend, isTrue);
    });

    test('an upload is JSON text, so it cannot be changed after approval', () {
      final (_, upload) = found().approve().startSending();
      expect(upload.body, isA<String>());
      expect(sent(upload), fullReport().toJson());
    });

    test('a send without an answer stays frozen: retry or withdraw', () {
      // The server may have stored it: its id must keep meaning this content.
      final unanswered = sending().sendFailed();
      expect(unanswered.status, ApprovalStatus.unanswered);
      expect(unanswered.maySend, isTrue);
      expect(
        () => unanswered.edit(fullReport().withoutLocation()),
        throwsStateError,
      );
      expect(unanswered.decline, throwsStateError);
      expect(unanswered.approve, throwsStateError);
      final (retrying, upload) = unanswered.startSending();
      expect(retrying.status, ApprovalStatus.sending);
      expect(upload.id, id);
      expect(sent(upload), fullReport().toJson());
      expect(unanswered.withdrawn().status, ApprovalStatus.withdrawn);
    });

    test('a refusal (413, 415, 422) is never sent again under its id', () {
      final refused = sending().refused();
      expect(refused.status, ApprovalStatus.refused);
      expect(refused.maySend, isFalse);
      expect(refused.startSending, throwsStateError);
      expect(() => refused.edit(fullReport()), throwsStateError);
      expect(refused.decline().status, ApprovalStatus.declined);
    });

    test('a refused report is revised as a new case, with a new id', () {
      const newId = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
      final revised = sending().refused().revise(
        id: newId,
        report: fullReport().withoutImage(),
      );
      expect(revised.status, ApprovalStatus.pending);
      expect(revised.id, newId);
      expect(revised.report.image, isNull);
      expect(
        () => sending().refused().revise(id: id, report: fullReport()),
        throwsArgumentError,
      );
      // The refused content itself is never sent again, under any id.
      expect(
        () => sending().refused().revise(id: newId, report: fullReport()),
        throwsArgumentError,
      );
      expect(
        () => found().revise(id: newId, report: fullReport()),
        throwsStateError,
      );
    });

    test('ends with the receipt, after which only withdrawal remains', () {
      final received = sending().received();
      expect(received.status, ApprovalStatus.received);
      expect(received.maySend, isFalse);
      expect(() => received.edit(fullReport()), throwsStateError);
      expect(received.withdrawn().status, ApprovalStatus.withdrawn);
    });

    test('a report withdrawn elsewhere (410) ends withdrawn', () {
      expect(sending().withdrawn().status, ApprovalStatus.withdrawn);
    });
  });

  test('withdrawal needs a report the server has or may have', () {
    expect(found().withdrawn, throwsStateError);
    expect(found().approve().withdrawn, throwsStateError);
  });
}
