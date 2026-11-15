/// Bounded HTTPS deletion transport. Redirects never receive bearer
/// credentials.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/device_record.dart';

final class HttpDeleteSubmitter implements DeleteSubmitter {
  new({http.Client? client, this.timeout = const Duration(seconds: 30)})
    : _client = client ?? http.Client();

  final http.Client _client;
  final Duration timeout;

  @override
  Future<DeletionReceipt> delete(DeviceEnrollment device) async {
    final aborted = Completer<void>();
    try {
      return await _request(device, aborted.future).timeout(timeout);
    } on DeletionFailure {
      rethrow;
    } on Exception {
      // No transport exception, URL or bearer secret becomes user-facing text.
      throw const DeletionFailure(DeletionProblem.unconfirmed);
    } finally {
      aborted.complete();
    }
  }

  Future<DeletionReceipt> _request(
    DeviceEnrollment device,
    Future<void> abort,
  ) async {
    final request =
        http.AbortableRequest('DELETE', device.deletionUri, abortTrigger: abort)
          ..followRedirects = false
          ..headers['Authorization'] = 'Bearer ${device.token}'
          ..headers['Accept'] = 'application/json';
    final response = await _client.send(request);
    if (response.statusCode != 200) {
      // Cancel the stream without buffering an arbitrary error response.
      await response.stream.listen(null).cancel();
      throw DeletionFailure(
        response.statusCode == 401
            ? DeletionProblem.unauthorized
            : DeletionProblem.unconfirmed,
      );
    }
    final bytes = <int>[];
    await for (final chunk in response.stream) {
      if (bytes.length + chunk.length > 4096) {
        throw const DeletionFailure(DeletionProblem.unconfirmed);
      }
      bytes.addAll(chunk);
    }
    return DeletionReceipt.parse(utf8.decode(bytes));
  }

  @override
  void close() => _client.close();
}
