"""Constructed pixel counts exercise denominators; no external benchmark fixture."""

from weedz.region_evaluation.sparse_aggregate import aggregate_sparse


def case(identity, pixels, covered, *, source="cwfid", digest=None):
    return {
        "sample_id": identity,
        "source": source,
        "image_sha256": digest or identity,
        "proposal_status": "ok",
        "labels": [
            {
                "category": "weed",
                "taxon": None,
                "budgets": [
                    {
                        "budget": 10,
                        "assessed_labelled_pixels": pixels,
                        "covered_labelled_pixels": covered,
                        "excluded_labelled_pixels": 0,
                    }
                ],
            }
        ],
    }


def test_micro_and_macro_positive_pixel_coverage_have_explicit_denominators():
    report = aggregate_sparse([case("1", 10, 5), case("2", 90, 0), case("3", 0, 0)])
    row = report["aggregate"][0]
    assert row["assessed_labelled_pixels"] == 100
    assert row["micro_positive_pixel_coverage"] == 0.05
    assert row["macro_image_positive_pixel_coverage"] == 0.25
    assert row["images_with_assessed_positive_pixels"] == 2
    assert "precision" not in row and "iou" not in row


def test_functional_category_names_do_not_pool_across_source_namespaces():
    report = aggregate_sparse([case("1", 10, 5), case("2", 10, 0, source="other")])
    assert len(report["aggregate"]) == 2


def test_duplicate_pixels_block_primary_aggregate():
    report = aggregate_sparse([case("1", 10, 5), case("2", 10, 0, digest="1")])
    assert report["aggregate"] is None
    assert report["duplicate_image_groups"] == [["1", "2"]]
