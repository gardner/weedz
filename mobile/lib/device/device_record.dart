/// Durable enrollment and deletion state, kept together in platform secure
/// storage.
library;

import 'dart:convert';

/// One atomic secure-storage value. Never store bearer credentials in
/// preferences.
abstract interface class DeviceRecordStore {
  Future<String?> read();
  Future<void> write(String record);
}

/// The operator's HTTPS intake service; credentials never enter its URL.
Uri intakeAddress(String value) {
  final uri = Uri.parse(value.trim());
  if (uri.scheme != 'https' ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment) {
    throw const FormatException(
      'Use an HTTPS address without credentials or query',
    );
  }
  return uri.replace(path: uri.path.endsWith('/') ? uri.path : '${uri.path}/');
}

/// Operator-issued credentials for exactly one intake service.
final class DeviceEnrollment {
  new({required String server, required String token})
    : server = intakeAddress(server),
      token = token.trim() {
    if (!RegExp(r'^weedzsub_[0-9]{1,18}_[A-Za-z0-9_-]{32,}$')
        .hasMatch(this.token)) {
      throw const FormatException(
        'Use the submitter token issued for this phone',
      );
    }
  }

  final Uri server;
  final String token;

  Uri get deletionUri => server.resolve('submitter');
}

/// A confirmed receipt. HTTP success alone is insufficient to clear
/// credentials.
final class DeletionReceipt {
  const new({required this.requestedAt, required this.completedAt});

  factory parse(String body) {
    final value = jsonDecode(body);
    if (value is! Map<String, dynamic> || value['status'] != 'deleted') {
      throw const FormatException('Deletion completion not confirmed');
    }
    final requested = _timestamp(value['requested_at']);
    final completed = _timestamp(value['completed_at']);
    if (completed.isBefore(requested)) {
      throw const FormatException('Invalid completion order');
    }
    return DeletionReceipt(requestedAt: requested, completedAt: completed);
  }

  final DateTime requestedAt;
  final DateTime completedAt;
}

DateTime _timestamp(Object? value) {
  final format = RegExp(
    r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})'
    r'(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$',
  );
  if (value is! String) {
    throw const FormatException('Expected a timestamp with time zone');
  }
  final match = format.firstMatch(value);
  if (match == null) {
    throw const FormatException('Expected a timestamp with time zone');
  }
  final year = int.parse(match[1]!);
  final month = int.parse(match[2]!);
  final day = int.parse(match[3]!);
  final date = DateTime.utc(year, month, day);
  final zone = match[7]!;
  if (date.year != year ||
      date.month != month ||
      date.day != day ||
      int.parse(match[4]!) > 23 ||
      int.parse(match[5]!) > 59 ||
      int.parse(match[6]!) > 59 ||
      (zone != 'Z' &&
          (int.parse(zone.substring(1, 3)) > 23 ||
              int.parse(zone.substring(4)) > 59))) {
    throw const FormatException('Invalid calendar timestamp');
  }
  return DateTime.parse(value).toUtc();
}

/// A single value prevents a crash between saving deletion intent and its
/// token.
final class DeviceRecord {
  const new({required this.device, this.pending = false, this.completedAt});

  factory parse(String text) {
    final value = jsonDecode(text);
    if (value is! Map<String, dynamic> || value['schema'] != 1) {
      throw const FormatException('Unknown secure enrollment record');
    }
    if (value['status'] == 'deleted') {
      return DeviceRecord(
        device: null,
        completedAt: _timestamp(value['completed_at']),
      );
    }
    if (value['status'] != 'enrolled' ||
        value['pending'] is! bool ||
        value['server'] is! String ||
        value['token'] is! String) {
      throw const FormatException('Invalid secure enrollment record');
    }
    return DeviceRecord(
      device: DeviceEnrollment(
        server: value['server'] as String,
        token: value['token'] as String,
      ),
      pending: value['pending'] as bool,
    );
  }

  final DeviceEnrollment? device;
  final bool pending;
  final DateTime? completedAt;

  String encode() => jsonEncode({
    'schema': 1,
    if (device case final device?) ...{
      'status': 'enrolled',
      'server': device.server.toString(),
      'token': device.token,
      'pending': pending,
    } else ...{
      'status': 'deleted',
      'completed_at': completedAt!.toUtc().toIso8601String(),
    },
  });
}
