"""A supported 1,000-sample synthetic review batch fits structural, not raw-export, caps."""

import hashlib
import json
from dataclasses import replace

from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews
from weedz.contract import Annotation, Sample, revise_sample


def test_thousand_samples_with_five_proposals_and_two_human_boxes(tmp_path):
    request, template, _ = inputs(tmp_path)
    root = request.package
    source = Sample.model_validate(
        json.loads((root / "private/provenance.json").read_bytes())["samples"][0]["sample"]
    )
    models = tuple(
        Annotation(
            id=f"proposal-{i}",
            supervision="box",
            taxon="Ulex europaeus",
            label="present",
            box=(1, 1, 8, 8),
            origin="model",
            model="synthetic-fixture",
        )
        for i in range(5)
    )
    original_task = json.loads((root / "tasks.json").read_bytes())[0]
    originals, canonical, exported = [], [], []
    for number in range(1000):
        sample = revise_sample(
            source, id=f"fixture:{number}", source_id=str(number), annotations=models
        )
        key = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
        originals.append({"external_id": key, "sample": sample.model_dump(mode="json")})
        task = json.loads(json.dumps(original_task))
        task["meta"]["external_id"] = key
        canonical.append(task)
        reviewed = json.loads(json.dumps(template))
        reviewed["id"] = number + 1
        reviewed["meta"]["external_id"] = key
        annotation = reviewed["annotations"][0]
        annotation.update(id=number + 1001, task=number + 1)
        for box in range(2):
            annotation["result"].append(
                dict(
                    id=f"box-{box}",
                    from_name="review_boxes",
                    to_name="image",
                    type="rectanglelabels",
                    original_width=10,
                    original_height=10,
                    image_rotation=0,
                    value=dict(
                        x=10,
                        y=10,
                        width=60,
                        height=60,
                        rotation=0,
                        rectanglelabels=["Ulex europaeus"],
                    ),
                )
            )
        exported.append(reviewed)
    receipt = json.loads((root / "manifest.json").read_bytes())
    for name, value in (
        ("tasks.json", canonical),
        ("private/provenance.json", {"samples": originals}),
    ):
        raw = json.dumps(value).encode()
        (root / name).write_bytes(raw)
        receipt["files"][name] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(receipt).encode()
    (root / "manifest.json").write_bytes(raw)
    request.export.write_text(json.dumps(exported), encoding="utf-8")
    request = replace(
        request,
        package_sha256=hashlib.sha256(raw).hexdigest(),
        export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest(),
    )
    output = tmp_path / "thousand-reviewed"
    result = import_reviews(request, output)
    assert result["imported_revisions"] == len(result["task_bindings"]) == 1000
    assert request.export.stat().st_size < 8 * 1024 * 1024
    assert 8 * 1024 * 1024 < (output / "private/provenance.json").stat().st_size < 64 * 1024 * 1024
