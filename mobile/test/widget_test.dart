import 'package:flutter_test/flutter_test.dart';
import 'package:weedz/main.dart';

void main() {
  testWidgets('the shell promises nothing is sent without approval', (
    tester,
  ) async {
    await tester.pumpWidget(const WeedzApp());
    expect(find.textContaining('after you approve each one'), findsOneWidget);
  });
}
