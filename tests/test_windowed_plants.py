import numpy as np
import pytest
from PIL import Image

from weedz.segmentation.windowed import plant_windows, source_mask, viewing_mask, whole_crop


def test_overlapping_windows_cover_edges_and_interior():
    windows = plant_windows((101, 77))
    assert windows[0] == (0, 0, 101, 77)
    assert len(set(windows)) == 5
    covered = np.zeros((77, 101), dtype=bool)
    for left, top, right, bottom in windows[1:]:
        assert 0 <= left < right <= 101 and 0 <= top < bottom <= 77
        covered[top:bottom, left:right] = True
    assert covered.all()
    assert windows[1][2] > windows[2][0]


def test_projection_preserves_native_pixel_coordinates():
    mask = np.array([[False, True], [True, False]])
    box, cropped = source_mask(mask, (10, 20, 14, 24))
    assert box == (10, 20, 14, 24)
    expected = np.repeat(np.repeat(mask, 2, axis=0), 2, axis=1)
    assert np.array_equal(cropped, expected)


@pytest.mark.parametrize("size,preview", [((19, 13), (8, 7)), ((9, 7), (4, 3)), ((7, 5), (13, 11))])
def test_view_mask_matches_full_canvas_nearest_resize(size, preview):
    mask = np.array([[True, False, True], [False, True, False]], dtype=bool)
    box = (2, 1, 5, 3)
    canvas = Image.new("L", size)
    canvas.paste(Image.fromarray(mask.astype(np.uint8) * 255), box[:2])
    expected = np.array(canvas.resize(preview, Image.Resampling.NEAREST)) > 0
    assert np.array_equal(viewing_mask(mask, box, size, preview), expected)


def test_complete_crop_has_guard_border_for_released_center_crop():
    image = Image.new("RGB", (80, 20), "red")
    padded = whole_crop(image)
    assert padded.width == padded.height and padded.width >= 89
    assert padded.getpixel((padded.width // 2, padded.height // 2)) == (255, 0, 0)
    assert padded.getpixel((0, 0)) == (128, 128, 128)


def test_geometry_rejects_invalid_masks_and_windows():
    with pytest.raises(ValueError):
        plant_windows((0, 12))
    with pytest.raises(ValueError):
        source_mask(np.ones((2, 2), dtype=np.float32), (0, 0, 10, 10))
    with pytest.raises(ValueError):
        source_mask(np.zeros((2, 2), dtype=bool), (0, 0, 10, 10))


def test_view_projection_matches_pillow_at_many_rounding_boundaries():
    for width in range(3, 15):
        for view_width in range(2, 17):
            size, preview = (width, 9), (view_width, 7)
            roi = np.array([[True, False], [False, True]], dtype=bool)
            box = (1, 2, 3, 4)
            canvas = Image.new("L", size)
            canvas.paste(Image.fromarray(roi.astype(np.uint8) * 255), box[:2])
            expected = np.array(canvas.resize(preview, Image.Resampling.NEAREST)) > 0
            assert np.array_equal(viewing_mask(roi, box, size, preview), expected)


def test_extreme_crop_has_bounded_padding_memory():
    padded = whole_crop(Image.new("RGB", (10000, 2)))
    assert max(padded.size) <= 1112


@pytest.mark.parametrize("vertical", [False, True])
def test_extreme_source_preview_uses_bounded_memory(vertical):
    import tracemalloc

    size = (1, 40_000_000) if vertical else (40_000_000, 1)
    preview = (1, 4) if vertical else (4, 1)
    box = (0, 5_000_000, 1, 5_000_001) if vertical else (5_000_000, 0, 5_000_001, 1)
    mask = np.ones((1, 1), dtype=bool)
    tracemalloc.start()
    try:
        projected = viewing_mask(mask, box, size, preview)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    expected = np.array([[True, False, False, False]])
    assert np.array_equal(projected, expected.T if vertical else expected)
    assert peak_bytes < 1_000_000


@pytest.mark.parametrize("vertical", [False, True])
def test_preview_preserves_pillow_incremental_rounding_tie(vertical):
    mask = np.array([[True, False]])
    size, preview = (2, 1), (7, 1)
    if vertical:
        mask, size, preview = mask.T, (1, 2), (1, 7)
    # Pillow's incremental additions sample source zero at the central pixel;
    # computing each coordinate independently would incorrectly sample source one.
    expected = np.array([[True, True, True, True, False, False, False]])
    assert np.array_equal(
        viewing_mask(mask, (0, 0, size[0], size[1]), size, preview),
        expected.T if vertical else expected,
    )
