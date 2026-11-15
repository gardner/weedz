/// A downloaded bundle is unsupported, inconsistent, or not trusted.
class BundleRejected implements Exception {
  const new(this.message);
  final String message;
  @override
  String toString() => 'BundleRejected: $message';
}

Map<String, Object?> object(Object? value) {
  if (value is! Map<String, Object?>) {
    throw const BundleRejected('Expected an object');
  }
  return value;
}

List<Object?> array(Object? value) {
  if (value is! List<Object?>) throw const BundleRejected('Expected an array');
  return value;
}

String text(Object? value) {
  if (value is! String) throw const BundleRejected('Expected text');
  return value;
}

int integer(Object? value, {int minimum = 0}) {
  if (value is! int || value < minimum || value > 9007199254740991) {
    throw const BundleRejected('Expected a bounded integer');
  }
  return value;
}

Object? frozen(Object? value) {
  if (value is Map<String, Object?>) {
    return Map<String, Object?>.unmodifiable(
      value.map((key, item) => MapEntry(key, frozen(item))),
    );
  }
  if (value is List<Object?>) {
    return List<Object?>.unmodifiable(value.map(frozen));
  }
  return value;
}
