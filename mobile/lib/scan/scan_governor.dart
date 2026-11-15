/// Whether the phone can take more scanning right now (#53).
library;

abstract interface class ScanGovernor {
  /// False when the phone is hot, the battery is low, or the OS asks the app
  /// to stop. The scan then rests and can be resumed later.
  Future<bool> mayContinue();
}

/// Never asks the scan to rest: a stand-in until real thermal and battery
/// signals are wired up.
final class AlwaysContinue implements ScanGovernor {
  const new();

  @override
  Future<bool> mayContinue() async => true;
}
