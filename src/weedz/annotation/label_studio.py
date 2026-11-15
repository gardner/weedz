"""Label Studio predictions: raw model evidence and class-agnostic mask proposals."""

import base64
import hashlib
import io
import json
from typing import Any, Literal
from urllib.parse import quote

import numpy as np
from PIL import Image

from weedz.annotation.serialization import result_json

Mode = Literal["assisted", "blind"]
PROPOSAL = "Model-proposed region"


def external_id(source_id: str, image_sha256: str) -> str:
    """Identity is independent of model/run; changed image bytes are a different task."""
    return hashlib.sha256(f"inaturalist:{source_id}:{image_sha256}".encode()).hexdigest()


def model_version(kind: str, metadata: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return f"{kind}:{digest}"


def mask_prediction(
    region: dict[str, Any], size: tuple[int, int], label: str = PROPOSAL
) -> tuple[dict[str, Any], bytes]:
    from label_studio_sdk.converter.brush import mask2rle

    try:
        encoded = base64.b64decode(region["mask_png"], validate=True)
        with Image.open(io.BytesIO(encoded)) as image:
            if image.mode != "RGBA" or list(image.size) != region["mask_size"]:
                raise ValueError("Mask geometry or RGBA format does not match its record")
            if image.width * image.height > 40_000_000:
                raise ValueError("Mask exceeds experiment geometry limits")
            alpha = image.getchannel("A").resize(size, Image.Resampling.NEAREST)
        mask = np.asarray(alpha, dtype=np.uint8)
        mask = np.where(mask > 0, 255, 0).astype(np.uint8)
    except (OSError, KeyError, TypeError) as error:
        raise ValueError("Invalid model mask") from error
    if not mask.any():
        raise ValueError("A proposed region must have foreground pixels")
    normalized = io.BytesIO()
    Image.fromarray(mask).save(normalized, format="PNG")
    width, height = size
    for key in ("box", "context_box"):
        box = region[key]
        if len(box) != 4 or not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
            raise ValueError("Model region lies outside the source image")
    return {
        "id": str(region["id"]),
        "from_name": "regions",
        "to_name": "image",
        "type": "brushlabels",
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "value": {"format": "rle", "rle": mask2rle(mask), "brushlabels": [label]},
    }, normalized.getvalue()


def evidence_result(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "model-evidence",
        "from_name": "model_evidence",
        "to_name": "image",
        "type": "textarea",
        "readonly": True,
        "value": {"text": [result_json(evidence)]},
    }


def task(
    source_id: str,
    digest: str,
    scores: dict[str, Any],
    model: dict[str, Any],
    size: tuple[int, int],
    mode: Mode,
    image_prefix: str = "corpus",
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    result: dict[str, Any] = {
        "data": {"image": f"/data/local-files/?d={quote(f'{image_prefix}/{digest}.png')}"},
        "meta": {"external_id": external_id(source_id, digest)},
    }
    masks: list[tuple[str, bytes]] = []
    if mode == "blind":
        return result, masks
    baseline = {key: value for key, value in model.items() if key != "proposal_experiment"}
    predictions = [
        {
            "model_version": model_version("bioclip-baseline", baseline),
            "result": [
                evidence_result(
                    {
                        "interpretation": (
                            "Uncalibrated watchlist comparisons, "
                            "not species identification or confidence"
                        ),
                        "score_kind": "target-minus-strongest-comparison cosine margin",
                        "watchlist_comparisons": scores.get("species", []),
                    }
                )
            ],
        }
    ]
    segmentation = scores.get("segmentation")
    if segmentation:
        regions = segmentation.get("regions", [])
        proposal_status = segmentation.get("proposal_status", segmentation.get("status"))
        if proposal_status not in {"ok", "empty", "failed"}:
            raise ValueError("Unknown segmentation result status")
        if proposal_status != "ok" and regions:
            raise ValueError("Non-successful segmentation cannot contain proposed regions")
        brush_results = []
        for region in regions:
            brush, encoded = mask_prediction(region, size)
            brush_results.append(brush)
            masks.append((hashlib.sha256(encoded).hexdigest(), encoded))
        predictions.append(
            {
                "model_version": model_version("sam-bioclip", model),
                "result": [
                    *brush_results,
                    evidence_result(
                        {
                            "interpretation": (
                                "Class-agnostic model regions, not plant/species labels; "
                                "margins are not confidence"
                            ),
                            "status": segmentation["status"],
                            "proposal_status": proposal_status,
                            "view_status": segmentation.get("view_status", segmentation["status"]),
                            "region_comparisons": [
                                {"id": region["id"], "views": region.get("views", {})}
                                for region in regions
                            ],
                        }
                    ),
                ],
            }
        )
    result["predictions"] = predictions
    return result, masks


def label_config(mode: Mode) -> str:
    model_label = f'<Label value="{PROPOSAL}" background="#888888"/>' if mode == "assisted" else ""
    evidence = (
        (
            '<TextArea name="model_evidence" toName="image" editable="false" '
            'rows="5" maxSubmissions="1"/>'
        )
        if mode == "assisted"
        else ""
    )
    return f"""<View>
  <Header value="Annotate visible regions; model proposals are not verified labels."/>
  <Image name="image" value="$image"/>
  <Header value="Verify, correct or clear the image taxon before submitting."/>
  <TextArea name="predicted_taxon" toName="image" editable="true" rows="1" maxSubmissions="1"/>
  <Header value="Check the whole image, including regions without model masks."/>
  <Choices name="plant_presence" toName="image" choice="single" required="true">
    <Choice value="Plant visible"/><Choice value="No plant visible"/><Choice value="Unsure"/>
  </Choices>
  <Header value="Any watchlist plant: gorse, old man's beard or pampas grass?"/>
  <Choices name="watchlist_presence" toName="image" choice="single" required="true">
    <Choice value="Watchlist plant visible"/><Choice value="No watchlist plant visible"/>
    <Choice value="Unsure"/>
  </Choices>
  <Choices name="watchlist_species" toName="image" choice="multiple" required="true"
    visibleWhen="choice-selected" whenTagName="watchlist_presence"
    whenChoiceValue="Watchlist plant visible">
    <Choice value="Ulex europaeus"/><Choice value="Clematis vitalba"/>
    <Choice value="Cortaderia selloana"/>
  </Choices>
  <Header value="Any other plants visible?"/>
  <Choices name="other_plant_presence" toName="image" choice="single" required="true">
    <Choice value="Other plant visible"/><Choice value="No other plant visible"/>
    <Choice value="Unsure"/>
  </Choices>
  <BrushLabels name="regions" toName="image">
    {model_label}
    <Label value="Ulex europaeus" background="#e8be36"/>
    <Label value="Clematis vitalba" background="#4ca868"/>
    <Label value="Cortaderia selloana" background="#b985d5"/>
    <Label value="Other plant" background="#44aaaa"/>
    <Label value="Non-plant" background="#cc7777"/>
    <Label value="Unknown" background="#777777"/>
  </BrushLabels>
  <TextArea name="region_taxon" toName="image" perRegion="true" editable="true"
    displayMode="region-list" rows="1" maxSubmissions="1"/>
  {evidence}
</View>
"""
