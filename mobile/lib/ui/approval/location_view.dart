/// The exact location a report shares, as numbers and as a pin with its
/// accuracy circle.
///
/// There is no map underneath on purpose (#56): map tiles would send the
/// exact location to a third host before the person has agreed to share it,
/// and map SDKs need keys and track their users.
library;

import 'package:material_ui/material_ui.dart';
import 'package:weedz/domain/report.dart';

/// One sentence a screen reader reads for [location].
String locationSentence(Location location) =>
    'Exact location in this report: latitude ${location.latitude}, '
    'longitude ${location.longitude}, accurate to within '
    '${location.accuracyM} metres.';

/// The coordinates and accuracy as stored (full precision, never rounded:
/// exactly what is sent), and the diagram. A screen reader hears one
/// sentence for all of it, from [locationSentence].
class LocationView extends StatelessWidget {
  const new({required this.location, super.key});

  final Location location;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final metres = '${location.accuracyM}';
    return Semantics(
      container: true,
      label: locationSentence(location),
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AccuracyDiagram(metres: metres, colours: theme.colorScheme),
            const SizedBox(height: 12),
            SelectableText(
              'Latitude ${location.latitude}\n'
              'Longitude ${location.longitude}\n'
              'Accurate to within ±$metres m',
              style: theme.textTheme.bodyLarge?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A pin in the middle of its accuracy circle, with a scale bar the length
/// of the circle's radius.
class _AccuracyDiagram extends StatelessWidget {
  const new({required this.metres, required this.colours});

  final String metres;
  final ColorScheme colours;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AspectRatio(
          aspectRatio: 2,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: colours.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(12),
            ),
            child: CustomPaint(painter: _PinPainter(colours)),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'The circle shows the accuracy: the camera was within $metres m '
          'of the pin. The pin is where the camera was, not the plant.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _PinPainter extends CustomPainter {
  const new(this.colours);

  final ColorScheme colours;

  @override
  void paint(Canvas canvas, Size size) {
    final centre = size.center(Offset.zero);
    final radius = size.shortestSide / 3;
    canvas
      ..drawCircle(
        centre,
        radius,
        Paint()..color = colours.primary.withValues(alpha: 0.18),
      )
      ..drawCircle(
        centre,
        radius,
        Paint()
          ..color = colours.primary
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      )
      ..drawCircle(centre, 6, Paint()..color = colours.error)
      ..drawCircle(
        centre,
        6,
        Paint()
          ..color = colours.onError
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
    // The scale bar: one radius long, so it stands for the accuracy.
    final bar = Paint()
      ..color = colours.onSurface
      ..strokeWidth = 2;
    final y = size.height - 12;
    canvas
      ..drawLine(Offset(12, y), Offset(12 + radius, y), bar)
      ..drawLine(Offset(12, y - 4), Offset(12, y + 4), bar)
      ..drawLine(Offset(12 + radius, y - 4), Offset(12 + radius, y + 4), bar);
  }

  @override
  bool shouldRepaint(_PinPainter oldDelegate) => oldDelegate.colours != colours;
}
