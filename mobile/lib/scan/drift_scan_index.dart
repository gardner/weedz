/// The scan index in SQLite, through drift (#53).
///
/// It uses plain SQL rather than drift's generated tables: two small tables
/// do not justify a code generator in the build.
library;

import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/scan_index.dart';
import 'package:weedz/scan/screener.dart';

const _schema = [
  '''
  CREATE TABLE scan_assets (
    id TEXT PRIMARY KEY NOT NULL,
    modified_at INTEGER NOT NULL,
    seen_in_pass INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('seen', 'screened', 'skipped')),
    model_revision TEXT,
    margins TEXT,
    skip_reason TEXT
  )''',
  'CREATE INDEX scan_assets_pass ON scan_assets (seen_in_pass)',
  '''
  CREATE TABLE scan_position (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    pass INTEGER NOT NULL,
    cursor_created_at INTEGER,
    cursor_id TEXT
  )''',
  'INSERT INTO scan_position (singleton, pass) VALUES (1, 0)',
];

final class _Database extends GeneratedDatabase {
  new(super.executor);

  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const [];

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (_) async {
      for (final statement in _schema) {
        await customStatement(statement);
      }
    },
  );
}

final class DriftScanIndex implements ScanIndex {
  /// Opens the index on [executor]: a file on the phone, or memory in tests.
  new(QueryExecutor executor) : _db = _Database(executor);

  final _Database _db;

  Future<void> close() => _db.close();

  @override
  Future<ScanPosition> position() async {
    final row = await _db
        .customSelect(
          'SELECT pass, cursor_created_at, cursor_id FROM scan_position',
        )
        .getSingle();
    final micros = row.read<int?>('cursor_created_at');
    final id = row.read<String?>('cursor_id');
    return ScanPosition(
      pass: row.read<int>('pass'),
      cursor: micros == null || id == null
          ? null
          : ScanCursor(createdAt: _time(micros), id: id),
    );
  }

  @override
  Future<Map<String, AssetRecord>> recordsFor(Iterable<String> ids) async {
    final wanted = ids.toList();
    final found = <String, AssetRecord>{};
    // SQLite limits bound variables per statement, so ask in chunks.
    for (var i = 0; i < wanted.length; i += 500) {
      final chunk = wanted.sublist(i, (i + 500).clamp(0, wanted.length));
      final rows = await _db
          .customSelect(
            'SELECT * FROM scan_assets '
            'WHERE id IN (${List.filled(chunk.length, '?').join(', ')})',
            variables: [for (final id in chunk) Variable.withString(id)],
          )
          .get();
      for (final row in rows) {
        final record = _record(row);
        found[record.id] = record;
      }
    }
    return found;
  }

  @override
  Future<void> save(
    List<AssetRecord> records, {
    required ScanCursor? cursor,
  }) => _db.transaction(() async {
    for (final record in records) {
      await _db.customInsert(
        'INSERT OR REPLACE INTO scan_assets (id, modified_at, seen_in_pass, '
        'state, model_revision, margins, skip_reason) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        variables: _variables(record),
      );
    }
    await _db.customUpdate(
      'UPDATE scan_position SET cursor_created_at = ?, cursor_id = ?',
      variables: [
        Variable<int>(cursor?.createdAt.microsecondsSinceEpoch),
        Variable<String>(cursor?.id),
      ],
    );
  });

  @override
  Future<void> finishPass() => _db.transaction(() async {
    await _db.customStatement(
      'DELETE FROM scan_assets WHERE seen_in_pass < '
      '(SELECT pass FROM scan_position)',
    );
    await _db.customStatement(
      'UPDATE scan_position SET pass = pass + 1, '
      'cursor_created_at = NULL, cursor_id = NULL',
    );
  });

  @override
  Future<IndexSummary> summary(String modelRevision) async {
    final rows = await _db
        .customSelect(
          'SELECT state, skip_reason, model_revision = ? AS current, '
          'COUNT(*) AS n FROM scan_assets GROUP BY 1, 2, 3',
          variables: [Variable.withString(modelRevision)],
        )
        .get();
    var screened = 0;
    var waiting = 0;
    final skipped = <SkipReason, int>{};
    for (final row in rows) {
      final n = row.read<int>('n');
      switch (row.read<String>('state')) {
        case 'screened' when row.read<bool?>('current') ?? false:
          screened += n;
        case 'skipped':
          final reason = SkipReason.values.byName(
            row.read<String>('skip_reason'),
          );
          skipped[reason] = (skipped[reason] ?? 0) + n;
        case 'seen':
          waiting += n;
      }
    }
    return IndexSummary(screened: screened, skipped: skipped, waiting: waiting);
  }
}

DateTime _time(int micros) =>
    DateTime.fromMicrosecondsSinceEpoch(micros, isUtc: true);

List<Variable> _variables(AssetRecord record) {
  final (state, revision, margins, reason) = switch (record) {
    SeenAsset() => ('seen', null, null, null),
    ScreenedAsset(:final modelRevision, :final margins) => (
      'screened',
      modelRevision,
      jsonEncode(margins),
      null,
    ),
    SkippedAsset(:final reason) => ('skipped', null, null, reason.name),
  };
  return [
    Variable.withString(record.id),
    Variable.withInt(record.modifiedAt.microsecondsSinceEpoch),
    Variable.withInt(record.seenInPass),
    Variable.withString(state),
    Variable<String>(revision),
    Variable<String>(margins),
    Variable<String>(reason),
  ];
}

AssetRecord _record(QueryRow row) {
  final id = row.read<String>('id');
  final modifiedAt = _time(row.read<int>('modified_at'));
  final pass = row.read<int>('seen_in_pass');
  return switch (row.read<String>('state')) {
    'screened' => ScreenedAsset(
      id: id,
      modifiedAt: modifiedAt,
      seenInPass: pass,
      modelRevision: row.read<String>('model_revision'),
      margins: _margins(row.read<String>('margins')),
    ),
    'skipped' => SkippedAsset(
      id: id,
      modifiedAt: modifiedAt,
      seenInPass: pass,
      reason: SkipReason.values.byName(row.read<String>('skip_reason')),
    ),
    _ => SeenAsset(id: id, modifiedAt: modifiedAt, seenInPass: pass),
  };
}

Margins _margins(String json) => {
  for (final MapEntry(:key, :value)
      in (jsonDecode(json) as Map<String, Object?>).entries)
    key: (value! as num).toDouble(),
};
