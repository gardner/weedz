/// How much of the photo library the person has let the app see (#53).
library;

enum PhotoAccess {
  /// The whole library.
  full,

  /// Only the photos the person chose: iOS limited access, or Android 14+
  /// `READ_MEDIA_VISUAL_USER_SELECTED`. The person can change the selection.
  limited,

  /// Nothing: refused, restricted by a parent or employer, or not asked yet.
  denied;

  bool get canScan => this != denied;

  /// A scan under this access covers only part of the library.
  bool get isPartial => this == limited;

  /// What a coverage report must add so nobody mistakes a partial scan for a
  /// whole one, or null when the scan covers the whole library.
  String? get coverageNote => switch (this) {
    full => null,
    limited => 'This covers only the photos you chose to share.',
    denied =>
      "Weedz can't see your photos. Allow photo access to scan them on "
          'this phone.',
  };
}
