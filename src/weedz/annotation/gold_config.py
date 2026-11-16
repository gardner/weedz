"""Opt-in review configuration; the historical prediction config stays unchanged."""

import hashlib
from html import escape


def gold_config(
    taxa: tuple[str, ...], categories: tuple[str, ...] = (), *, revision: int = 1
) -> str:
    if type(revision) is not int or revision not in (1, 2):
        raise ValueError("Unsupported human review configuration revision")
    if (not taxa and not categories) or len(set(taxa + categories)) != len(taxa + categories):
        raise ValueError("Declare a nonempty unique taxon/category scope")
    if any(not name.strip() for name in taxa + categories):
        raise ValueError("Scope labels must be nonempty")
    labels = "".join(f'<Label value="{escape(name, quote=True)}"/>' for name in taxa + categories)
    scopes = _scope_tags(taxa, categories, revision)
    image_rotation = ' rotateControl="false"' if revision == 2 else ""
    box_rotation = ' canRotate="false"' if revision == 2 else ""
    return f"""<View>
  <Header value="Human verification; submitting is not independent expert acceptance."/>
  <Image name="image" value="$image"{image_rotation}/>
  <Text name="photo_credit" value="$photo_credit" valueType="text" selectionEnabled="false"/>
  <RectangleLabels name="review_boxes" toName="image"{box_rotation}>{labels}</RectangleLabels>
  <BrushLabels name="regions" toName="image">{labels}</BrushLabels>
  <TextArea name="model_evidence" toName="image" editable="false" rows="3"/>
  <Header value="Declare your review decision explicitly. Expertise is not inferred."/>
  <Choices name="review_status" toName="image" choice="single" required="true">
    <Choice value="unreviewed"/><Choice value="accepted"/>
    <Choice value="uncertain"/><Choice value="rejected"/>
  </Choices>
  <Header value="Exhaustive means every visible instance in the selected scope is marked."/>
  <Choices name="completeness_task" toName="image" choice="single" required="true">
    <Choice value="detection"/><Choice value="segmentation"/>
  </Choices>
  <Choices name="completeness_status" toName="image" choice="single" required="true">
    <Choice value="exhaustive"/><Choice value="partial"/><Choice value="unknown"/>
  </Choices>
  {scopes}
</View>
"""


def _scope_tags(taxa: tuple[str, ...], categories: tuple[str, ...], revision: int) -> str:
    groups = (("taxa", taxa), ("categories", categories))
    if revision == 2:
        groups = (("scope", taxa + categories),)
    scopes = []
    for kind, names in groups:
        if names:
            choices = "".join(f'<Choice value="{escape(n, quote=True)}"/>' for n in names)
            required = ' required="true"' if revision == 2 else ""
            scopes.append(
                f'<Choices name="completeness_{kind}" toName="image" '
                f'choice="multiple"{required}>{choices}</Choices>'
            )
    return "".join(scopes)


def configuration_revision(
    taxa: tuple[str, ...], categories: tuple[str, ...], checksum: str
) -> int:
    for revision in (1, 2):
        raw = gold_config(taxa, categories, revision=revision).encode("utf-8")
        if hashlib.sha256(raw).hexdigest() == checksum:
            return revision
    raise ValueError("Configuration is not the declared canonical human review schema")
