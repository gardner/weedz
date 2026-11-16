from PIL import Image

from weedz.labelled.pixels import pixel_sha256


def test_pixel_identity_ignores_container_metadata_but_binds_geometry():
    original = Image.new("RGB", (2, 3), (10, 20, 30))
    same = original.copy()
    same.info["comment"] = "publisher metadata"
    assert pixel_sha256(original) == pixel_sha256(same)
    reshaped = Image.frombytes("RGB", (3, 2), original.tobytes())
    assert pixel_sha256(original) != pixel_sha256(reshaped)
