/// The phone's photo library through `photo_manager` (PhotoKit on iOS,
/// MediaStore on Android) (#53).
///
/// It only reads, and it never downloads an original from iCloud: a photo
/// that is not on the phone is skipped as cloud-only and counted.
library;

import 'package:photo_manager/photo_manager.dart';
import 'package:weedz/scan/library.dart';
import 'package:weedz/scan/photo_access.dart';
import 'package:weedz/scan/scan_index.dart';

PhotoAccess accessFrom(PermissionState state) => switch (state) {
  PermissionState.authorized => PhotoAccess.full,
  PermissionState.limited => PhotoAccess.limited,
  PermissionState.denied ||
  PermissionState.restricted ||
  PermissionState.notDetermined => PhotoAccess.denied,
};

/// Images only. Location (`ACCESS_MEDIA_LOCATION`) is asked for by #54.
const _permission = PermissionRequestOption(
  androidPermission: AndroidPermission(
    type: RequestType.image,
    mediaLocation: false,
  ),
);

final class PhotoManagerLibrary implements PhotoLibrary {
  /// [screeningSize] bounds the longer side of the image handed to the
  /// screener, scaled down on the phone.
  const new({this.screeningSize = 1024});

  final int screeningSize;

  @override
  Future<PhotoAccess> access() async => accessFrom(
    await PhotoManager.getPermissionState(requestOption: _permission),
  );

  @override
  Future<PhotoAccess> requestAccess() async => accessFrom(
    await PhotoManager.requestPermissionExtend(requestOption: _permission),
  );

  @override
  Future<void> changeSelection() =>
      PhotoManager.presentLimited(type: RequestType.image);

  @override
  Future<int> count() => PhotoManager.getAssetCount(
    type: RequestType.image,
    filterOption: _filter(),
  );

  @override
  Future<List<LibraryAsset>> olderThan(
    ScanCursor? cursor, {
    required int limit,
  }) => pageOlderThan(cursor, limit: limit, query: _query);

  Future<List<LibraryAsset>> _query({
    DateTime? newest,
    DateTime? oldest,
    int? limit,
  }) async {
    final filter = _filter(newest: newest, oldest: oldest);
    final end =
        limit ??
        await PhotoManager.getAssetCount(
          type: RequestType.image,
          filterOption: filter,
        );
    if (end == 0) return const [];
    final assets = await PhotoManager.getAssetListRange(
      start: 0,
      end: end,
      type: RequestType.image,
      filterOption: filter,
    );
    return [for (final a in assets) _asset(a)];
  }

  @override
  Future<LoadOutcome> load(LibraryAsset asset) async {
    final entity = await AssetEntity.fromId(asset.id);
    if (entity == null) return const ImageSkipped(SkipReason.unreadable);
    if (!await entity.isLocallyAvailable()) {
      return const ImageSkipped(SkipReason.cloudOnly);
    }
    final bytes = await entity.thumbnailDataWithSize(
      ThumbnailSize.square(screeningSize),
      quality: 90,
    );
    return bytes == null
        ? const ImageSkipped(SkipReason.unsupported)
        : ImageLoaded(ScanImage(bytes));
  }
}

/// Newest first, within an inclusive capture-time range. Without bounds the
/// plugin's default would leave out photos dated in the future.
FilterOptionGroup _filter({DateTime? newest, DateTime? oldest}) =>
    FilterOptionGroup(
      imageOption: const FilterOption(
        sizeConstraint: SizeConstraint(ignoreSize: true),
      ),
      createTimeCond: DateTimeCond(
        min: oldest ?? DateTime.utc(1800),
        max: newest ?? DateTime.utc(9999),
        ignore: newest == null && oldest == null,
      ),
      orders: const [OrderOption()], // By capture time, newest first.
    );

LibraryAsset _asset(AssetEntity a) => LibraryAsset(
  id: a.id,
  createdAt: a.createDateTime.toUtc(),
  modifiedAt: a.modifiedDateTime.toUtc(),
  width: a.width,
  height: a.height,
);
