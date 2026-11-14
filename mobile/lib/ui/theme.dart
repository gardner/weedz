/// The app's shared look, built for accessibility (#63): Material 3 colours
/// from one seed (its pairs meet WCAG 2.2 AA contrast), and every button at
/// least 48 dp square.
library;

import 'package:material_ui/material_ui.dart';

/// The smallest tap target on either platform (Android asks for 48 dp,
/// iOS for 44 pt).
const minTapTarget = 48.0;

ThemeData appTheme() {
  // Only a minimum height: an infinite minimum width breaks buttons in rows.
  // Screens that want full-width buttons stretch them.
  const buttonSize = Size(minTapTarget, minTapTarget);
  const buttonPadding = EdgeInsets.symmetric(horizontal: 16, vertical: 12);
  return ThemeData(
    colorSchemeSeed: Colors.green,
    materialTapTargetSize: MaterialTapTargetSize.padded,
    visualDensity: VisualDensity.standard,
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: buttonSize,
        padding: buttonPadding,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: buttonSize,
        padding: buttonPadding,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(minTapTarget, minTapTarget),
        padding: buttonPadding,
      ),
    ),
  );
}
