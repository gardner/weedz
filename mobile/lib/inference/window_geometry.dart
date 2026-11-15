import 'dart:math' as math;

/// Pixel edges in the EXIF-upright image, with exclusive right/bottom edges.
typedef PixelBox = ({int left, int top, int right, int bottom});

/// Python-compatible round-half-to-even for ranking revision 4.
int roundEven(double value) {
  final floor = value.floor();
  final fraction = value - floor;
  return fraction < 0.5 || (fraction == 0.5 && floor.isEven)
      ? floor
      : floor + 1;
}

List<int> _positions(int length, int side) {
  if (length <= side) return [0];
  final count = ((length - side) / (side * 0.75)).ceil() + 1;
  return List.generate(
    count,
    (i) => roundEven(i * (length - side) / (count - 1)),
  );
}

List<int> _thin(List<int> positions, int keep) {
  final step = (positions.length - 1) / math.max(1, keep - 1);
  return List.generate(
    keep,
    (i) => positions[roundEven(i * step)],
  ).toSet().toList()..sort();
}

/// Whole frame first, then deduplicated ranking-4 square tiles in row order.
List<PixelBox> regionBoxes(int width, int height) {
  if (width <= 0 || height <= 0 || width > 100000 || height > 100000) {
    throw ArgumentError('Image dimensions must be within 1..100000');
  }
  final side = math.max(1, roundEven(math.min(width, height) * 0.6));
  var xs = _positions(width, side);
  var ys = _positions(height, side);
  if (xs.length * ys.length > 32) {
    if (width >= height) {
      xs = _thin(xs, 32 ~/ ys.length);
    } else {
      ys = _thin(ys, 32 ~/ xs.length);
    }
  }
  return <PixelBox>{
    (left: 0, top: 0, right: width, bottom: height),
    for (final y in ys)
      for (final x in xs) (left: x, top: y, right: x + side, bottom: y + side),
  }.toList(growable: false);
}

List<int> boxEdges(PixelBox box) => [box.left, box.top, box.right, box.bottom];
