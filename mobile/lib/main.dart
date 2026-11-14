import 'package:material_ui/material_ui.dart';
import 'package:weedz/ui/theme.dart';

void main() {
  runApp(const WeedzApp());
}

/// The app shell. Scanning, approval and sending arrive with #53–#57; see
/// docs/mobile.md for the architecture.
class WeedzApp extends StatelessWidget {
  const new({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Weedz',
      theme: appTheme(),
      home: const Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Nothing is scanned or sent yet. Reports will leave this '
                'phone only after you approve each one.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
