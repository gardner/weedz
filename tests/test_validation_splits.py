"""Items always fall on the same side of the development / held-out split."""

import pytest

from weedz.validation.splits import split_of


def test_an_item_always_lands_in_the_same_split():
    assert split_of("openimages:0001eeaf4aed83f9") == split_of("openimages:0001eeaf4aed83f9")


def test_the_split_is_close_to_the_requested_fraction():
    held_out = sum(split_of(f"item-{n}") == "held-out" for n in range(10_000))
    assert 4_800 < held_out < 5_200


def test_a_new_salt_reshuffles_the_split():
    items = [f"item-{n}" for n in range(200)]
    assert [split_of(i) for i in items] != [split_of(i, salt="other") for i in items]


def test_the_fraction_must_be_a_proper_share():
    with pytest.raises(ValueError):
        split_of("a", held_out=1.0)
