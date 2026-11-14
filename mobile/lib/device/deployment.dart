import 'package:weedz/device/device_record.dart';

/// Supplied to the build with --dart-define; public service addresses, never
/// tokens.
final class DeviceDeployment {
  const new({
    this.intakeBaseUrl = const String.fromEnvironment('WEEDZ_INTAKE_BASE_URL'),
    this.deletionRequestUrl = const String.fromEnvironment(
      'WEEDZ_DELETION_REQUEST_URL',
    ),
  });

  final String intakeBaseUrl;
  final String deletionRequestUrl;

  /// Absence/invalid configuration must not create a misleading public contact.
  Uri? get publicDeletionRoute {
    if (deletionRequestUrl.isEmpty) return null;
    try {
      final uri = Uri.parse(deletionRequestUrl);
      if (uri.scheme != 'https' ||
          uri.host.isEmpty ||
          uri.userInfo.isNotEmpty) {
        return null;
      }
      return uri;
    } on FormatException {
      return null;
    }
  }

  String get enrollmentAddress {
    if (intakeBaseUrl.isEmpty) return '';
    try {
      return intakeAddress(intakeBaseUrl).toString();
    } on FormatException {
      return '';
    }
  }
}
