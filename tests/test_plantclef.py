import numpy as np
import pytest

from weedz.classification.plantclef import ranked_species


def test_topk_keeps_alternatives_and_normalizes_against_all_classes():
    rows = ranked_species(np.array([0.0, 0.0, 0.0, 0.0]), ("A", "B", "C", "D"), 2)
    assert [row["taxon"] for row in rows] == ["A", "B"]
    assert [row["score"] for row in rows] == [0.25, 0.25]
    assert {row["score_kind"] for row in rows} == {"closed_set_softmax_uncalibrated"}


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_output_is_failure_not_a_species_prediction(bad):
    with pytest.raises(ValueError, match="finite"):
        ranked_species(np.array([0.0, bad]), ("A", "B"), 1)


def test_class_mapping_cannot_silently_truncate_or_duplicate_species():
    with pytest.raises(ValueError, match="mapping"):
        ranked_species(np.array([1.0, 2.0]), ("A",), 1)
    with pytest.raises(ValueError, match="mapping"):
        ranked_species(np.array([1.0, 2.0]), ("A", "A"), 1)


@pytest.mark.parametrize("fail", [False, True])
def test_prediction_is_fp32_despite_ambient_tf32_and_autocast(fail):
    import torch
    from PIL import Image

    from weedz.classification.plantclef import PlantClassifier

    previous = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)

    def forward(batch):
        assert not torch.backends.cuda.matmul.allow_tf32
        assert not torch.backends.cudnn.allow_tf32
        assert not torch.is_autocast_enabled("cpu")
        assert batch.dtype == torch.float32
        if fail:
            raise RuntimeError("Interrupted forward")
        return torch.tensor([[1.0, 2.0]])

    classifier = PlantClassifier(
        forward,
        lambda _: torch.ones(3, 2, 2, dtype=torch.bfloat16),
        ("A", "B"),
        {"device": "cpu"},
    )
    try:
        for _ in range(2):
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            with torch.autocast("cpu", dtype=torch.bfloat16):
                if fail:
                    with pytest.raises(RuntimeError, match="Interrupted forward"):
                        classifier.predict([Image.new("RGB", (2, 2))], 2)
                else:
                    assert classifier.predict([Image.new("RGB", (2, 2))], 2)[0][0]["taxon"] == "B"
                assert torch.is_autocast_enabled("cpu")
                assert torch.backends.cuda.matmul.allow_tf32
                assert torch.backends.cudnn.allow_tf32
    finally:
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = previous
