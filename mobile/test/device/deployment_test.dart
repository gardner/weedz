import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/device/deployment.dart';

void main() {
  test(
    'deployment supplies the actual public route and enrollment address',
    () {
      const deployment = DeviceDeployment(
        intakeBaseUrl: 'https://intake.example.test/pilot',
        deletionRequestUrl: 'https://publisher.example.test/delete',
      );
      expect(
        deployment.enrollmentAddress,
        'https://intake.example.test/pilot/',
      );
      expect(
        deployment.publicDeletionRoute.toString(),
        'https://publisher.example.test/delete',
      );
    },
  );

  test('missing or unsafe configuration never invents a contact route', () {
    for (final url in [
      '',
      'http://publisher.example.test/delete',
      'https://secret@publisher.example.test/delete',
    ]) {
      expect(
        DeviceDeployment(deletionRequestUrl: url).publicDeletionRoute,
        isNull,
      );
    }
    expect(
      const DeviceDeployment(intakeBaseUrl: 'http://intake.example.test')
          .enrollmentAddress,
      isEmpty,
    );
  });
}
