"""Opt-in review configuration; the historical prediction config stays unchanged."""

from html import escape


def gold_config(taxa: tuple[str, ...], categories: tuple[str, ...] = ()) -> str:
    if (not taxa and not categories) or len(set(taxa + categories)) != len(taxa + categories):
        raise ValueError("Declare a nonempty unique taxon/category scope")
    if any(not name.strip() for name in taxa + categories):
        raise ValueError("Scope labels must be nonempty")
    labels = "".join(f'<Label value="{escape(name, quote=True)}"/>' for name in taxa + categories)
    scopes = []
    for kind, names in (("taxa", taxa), ("categories", categories)):
        if names:
            choices = "".join(f'<Choice value="{escape(n, quote=True)}"/>' for n in names)
            scopes.append(
                f'<Choices name="completeness_{kind}" toName="image" '
                f'choice="multiple">{choices}</Choices>'
            )
    return f"""<View>
  <Header value="Human verification; submitting is not independent expert acceptance."/>
  <Image name="image" value="$image"/>
  <Text name="photo_credit" value="$photo_credit" valueType="text" selectionEnabled="false"/>
  <RectangleLabels name="review_boxes" toName="image">{labels}</RectangleLabels>
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
  {"".join(scopes)}
</View>
"""
