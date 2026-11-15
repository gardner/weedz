/// The phone's photo library through `photo_manager` (PhotoKit on iOS,
/// MediaStore on Android) (#53).
///
/// It only reads, and it never downloads an original from iCloud: a photo
/// that is not on the phone is skipped as cloud-only and counted.
library;

import 'dart:math' as math;

import 'package:flutter/foundation.dart';
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
  /// [longSide] bounds the longer side of the image handed to the screener,
  /// scaled down on the phone with its aspect ratio kept.
  new({this.longSide = 1024});

  final int longSide;

  /// On Android, the SQL for the capture second photo_manager reports;
  /// null on iOS.
  late final Future<String?> _androidCapture =
      defaultTargetPlatform == TargetPlatform.android
      ? PhotoManager.systemVersion().then(
          (v) => androidCaptureSeconds(sdkInt: int.parse(v)),
        )
      : Future.value();

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
    filterOption: _darwinFilter(),
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
    final capture = await _androidCapture;
    final filter = capture == null
        ? _darwinFilter(newest: newest, oldest: oldest)
        : CustomFilter.sql(
            where: androidCaptureWhere(capture, newest: newest, oldest: oldest),
            orderBy: [OrderByItem.desc(capture), const OrderByItem.desc('_id')],
          );
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
    final size = screeningSize(
      width: entity.width,
      height: entity.height,
      longSide: longSide,
    );
    final bytes = await entity.thumbnailDataWithOption(
      defaultTargetPlatform == TargetPlatform.iOS
          // Aspect-fit and the final image, never a degraded first one.
          ? ThumbnailOption.ios(
              size: size,
              quality: 90,
              deliveryMode: DeliveryMode.highQualityFormat,
            )
          : ThumbnailOption(size: size, quality: 90),
    );
    // Null says only that the platform made no image this time (out of
    // memory, an IO error, the app backgrounded), not that the format is
    // unreadable, so the photo is retried next pass.
    return bytes == null
        ? const ImageSkipped(SkipReason.unreadable)
        : ImageLoaded(ScanImage(bytes));
  }
}

/// The size that shows the whole photo with its longer side at most
/// [longSide]. A square target would make PhotoKit crop to fill it.
ThumbnailSize screeningSize({
  required int width,
  required int height,
  required int longSide,
}) {
  final scale = longSide / math.max(width, height);
  if (scale >= 1) return ThumbnailSize(width, height);
  return ThumbnailSize(
    math.max(1, (width * scale).round()),
    math.max(1, (height * scale).round()),
  );
}

/// The SQL for the capture second photo_manager reports on Android, so the
/// scan filters and orders on the same value its cursor holds. From Android
/// 10 that is `datetaken` in seconds, or `date_added` when there is none;
/// before, `date_added`. The plugin's own date filter always uses
/// `date_added`, which differs after a restore to a new phone.
String androidCaptureSeconds({required int sdkInt}) => sdkInt >= 29
    ? '(CASE WHEN IFNULL(datetaken, 0) / 1000 = 0 THEN date_added '
          'ELSE datetaken / 1000 END)'
    : 'date_added';

/// An inclusive range on [capture], in whole seconds, as SQL.
String androidCaptureWhere(
  String capture, {
  DateTime? newest,
  DateTime? oldest,
}) => [
  if (newest != null)
    '$capture <= ${(newest.millisecondsSinceEpoch / 1000).floor()}',
  if (oldest != null)
    '$capture >= ${(oldest.millisecondsSinceEpoch / 1000).ceil()}',
].join(' AND ');

/// iOS: newest first by creation date, which is what photo_manager reports
/// there. Without bounds, the plugin's default would leave out photos dated
/// in the future.
FilterOptionGroup _darwinFilter({DateTime? newest, DateTime? oldest}) =>
    FilterOptionGroup(
      imageOption: const FilterOption(
        sizeConstraint: SizeConstraint(ignoreSize: true),
      ),
      createTimeCond: DateTimeCond(
        min: oldest ?? DateTime.utc(1800),
        max: newest ?? DateTime.utc(9999),
        ignore: newest == null && oldest == null,
      ),
      orders: const [OrderOption()], // By creation date, newest first.
    );

LibraryAsset _asset(AssetEntity a) => LibraryAsset(
  id: a.id,
  createdAt: a.createDateTime.toUtc(),
  modifiedAt: a.modifiedDateTime.toUtc(),
  width: a.width,
  height: a.height,
);
