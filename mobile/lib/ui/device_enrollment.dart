import 'package:material_ui/material_ui.dart';
import 'package:weedz/device/deletion.dart';
import 'package:weedz/device/device_record.dart';

/// Enrollment uses a credential issued by the operator for this phone.
class DeviceEnrollmentForm extends StatefulWidget {
  const new({
    required this.controller,
    required this.initialAddress,
    super.key,
  });

  final DeviceDeletion controller;
  final String initialAddress;

  @override
  State<DeviceEnrollmentForm> createState() => _DeviceEnrollmentFormState();
}

class _DeviceEnrollmentFormState extends State<DeviceEnrollmentForm> {
  late final _server = TextEditingController(text: widget.initialAddress);
  final _token = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _server.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    try {
      final enrollment = DeviceEnrollment(
        server: _server.text,
        token: _token.text,
      );
      _token.clear();
      setState(() => _error = null);
      await widget.controller.enroll(enrollment);
    } on FormatException {
      setState(
        () => _error =
            'Enter the operator’s HTTPS intake address and the submitter token '
            'issued for this phone.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Text('Set up this phone', style: TextStyle(fontSize: 20)),
      const Text(
        'Use the address and token supplied by your Weedz operator. '
        'Saving them does not upload a photo or verify access.',
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _server,
        decoration: const InputDecoration(labelText: 'Intake HTTPS address'),
        keyboardType: TextInputType.url,
        autocorrect: false,
        enabled: !widget.controller.busy,
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _token,
        decoration: const InputDecoration(labelText: 'Submitter token'),
        obscureText: true,
        autocorrect: false,
        enableSuggestions: false,
        enableIMEPersonalizedLearning: false,
        enabled: !widget.controller.busy,
      ),
      if (_error case final error?) Text(error, semanticsLabel: error),
      const SizedBox(height: 16),
      FilledButton(
        onPressed: widget.controller.busy ? null : _save,
        child: const Text('Save enrollment securely'),
      ),
    ],
  );
}
