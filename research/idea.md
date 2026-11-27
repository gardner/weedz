# AI invasive weed detection

**Date:** 2026-11-13
**Source:** chatgpt.com

---

### **You** · Fri, 13 Nov, 6:52 pm

Tell me about Using photos from iNaturalist to spot invasive weeds in the background. With AI of course.

---

### **ChatGPT** · Fri, 13 Nov, 6:52 pm

<small><strong>Reasoning / progress:</strong><br>
I’ll look at whether anyone is already doing this, what iNaturalist makes available, and how to build a system that finds background weeds without producing a flood of false positives. I’ll focus on New Zealand use cases too.</small>

# Using AI to find invasive weeds hiding in iNaturalist photographs

This is a compelling application of AI for ecological surveillance: **searching for invasive plants that nobody actually intended to photograph.**

Imagine someone uploads an iNaturalist observation of a butterfly. The butterfly is correctly identified, but behind it, growing along a fence, is an invasive climbing vine.

The observation is labelled *butterfly*, not *invasive vine*. Consequently, conventional species databases might never record the weed's presence.

A multimodal AI system could inspect the entire photograph, identify the vine, associate it with the observation's location and date, and flag a previously unknown infestation.

The particularly interesting part is that **New Zealand already has a closely related system, but there's an opportunity to extend its capabilities.**

## What's already happening in New Zealand?

<row align=start gap={3}>
  <AsyncImage query="New Zealand old man's beard invasive Clematis vitalba vine white fluffy seed heads tangled forest" aspectRatio="3:4" maxWidth="144px"/>
  <box flex="1" gap={1}>
    **<Entity category="organization" value="DOC Smart Weed Alert Tool (SWAT)"/>**

    The Department of Conservation's <Link url="https://weeds.doc.govt.nz/about" title="Smart Weed Alert Tool"/> automatically monitors biodiversity records from GBIF, including iNaturalist, looking for emerging weed incursions.

    It allows conservation groups, councils and biosecurity teams to receive alerts about invasive species occurring in particular areas. <Cite ref="turn690989search7"/>
  </box>
</row>

However, the distinction is fundamental:

| Existing SWAT approach | Proposed AI approach |
|---|---|
| Finds weeds already identified in biodiversity records | Finds weeds that appear incidentally in photographs |
| Uses species labels and geographic records | Uses visual evidence, species recognition and geographic records |
| Searches known observations | Generates previously unrecorded candidate occurrences |

SWAT provides a potential downstream destination for verified detections, rather than something you'd necessarily have to replace.

## 1. The dataset is enormous — and accessible

<box gap={2}>
  <row align="center" justify="between">
    <box gap={1}>
      <text color="secondary" weight="medium" size="xs">iNaturalist Open Dataset</text>
      <title size="2xl" color="default" tabularNums>400M+</title>
      <text color="secondary" size="xs">Photographs worldwide, according to its documentation</text>
    </box>
    <icon name="images" color="secondary" size="2xl"/>
  </row>
  The dataset is hosted on Amazon S3 and includes observation metadata, photo identifiers, dates, geographic coordinates, uncertainty and species labels. Metadata snapshots are updated monthly. <Cite ref="turn392704search3"/>
</box>

This is quite practical for a data-engineering pipeline. You don't need to scrape the website.

The official resources are <Link url="https://github.com/inaturalist/inaturalist-open-data" title="iNaturalist Open Data"/> and its <Link url="https://registry.opendata.aws/inaturalist-open-data/" title="AWS dataset"/>.

For a New Zealand pilot, filter the metadata geographically, prioritise photographs where the primary observation is **not a plant**, and retrieve those images for secondary analysis. Bird and insect photographs with visible vegetation may be particularly valuable.

The API is useful for recent observations, but iNaturalist explicitly advises against bulk scraping and recommends its datasets instead. <Cite ref="turn392704search2"/>

## 2. How I'd build the AI pipeline

<box border radius="xl" padding={3} gap={2} align="center">
  <box background="surface-secondary" radius="lg" padding={3} width="100%" align="center" gap={1}>
    <icon name="database" color="secondary" size="lg"/>
    **iNaturalist images + metadata**
    <caption>New Zealand, dated and georeferenced</caption>
  </box>
  <icon name="arrow-down" color="tertiary"/>
  <box background="surface-secondary" radius="lg" padding={3} width="100%" align="center" gap={1}>
    <icon name="scan-search" color="secondary" size="lg"/>
    **Locate secondary plants**
    <caption>Image tiling + open-vocabulary detection</caption>
  </box>
  <icon name="arrow-down" color="tertiary"/>
  <box background="surface-secondary" radius="lg" padding={3} width="100%" align="center" gap={1}>
    <icon name="brain-circuit" color="secondary" size="lg"/>
    **Identify candidate weeds**
    <caption>BioCLIP + visual reasoning + lookalike checks</caption>
  </box>
  <icon name="arrow-down" color="tertiary"/>
  <box background="surface-secondary" radius="lg" padding={3} width="100%" align="center" gap={1}>
    <icon name="shield-check" color="secondary" size="lg"/>
    **Validate and prioritise**
    <caption>Expert review + distribution and location checks</caption>
  </box>
  <icon name="arrow-down" color="tertiary"/>
  <box background="rgba(22,163,74,0.07)" border={{size:1,color:"rgba(22,163,74,0.25)"}} radius="lg" padding={3} width="100%" align="center" gap={1}>
    <icon name="map-pinned" color="success" size="lg"/>
    **Candidate weed-occurrence map**
    <caption>Evidence, confidence and original observation links</caption>
  </box>
</box>

There are already useful models for the individual stages.

| Component | Candidate technology |
|---|---|
| Open-vocabulary object detection | <Link url="https://github.com/IDEA-Research/GroundingDINO" title="Grounding DINO"/> |
| Species classification | <Link url="https://github.com/Imageomics/bioclip-2" title="BioCLIP 2 / 2.5"/> |
| Detailed segmentation, if needed | SAM 2 |
| Image reasoning and verification | Multimodal vision-language model |
| Spatial analysis | PostGIS, DuckDB, GeoPandas |
| Human review | Annotated image crops linked to observations |

BioCLIP 2 is especially interesting. Its researchers trained a biological vision model on approximately 200 million images, and released BioCLIP 2.5 Huge in February 2026. It is worth benchmarking on individual plant crops rather than assuming it can reliably identify tiny plants within entire landscape images. <Cite ref="turn800335search5"/>

I would first benchmark a general vision model against a detector-plus-specialist-classifier pipeline. The additional complexity is worthwhile only if it measurably improves recall at a manageable false-positive rate.

## 3. Which weeds are good candidates?

<grid columns={2} gap={3}>
  <grid-item>
    <AsyncImage query="Clematis vitalba old mans beard weed climbing tree New Zealand white fluffy seed clusters" aspectRatio="5:4"/>
    **Old man's beard**

    <text color="secondary" size="xs">Distinctive climbing habit and seed heads. Promising in forest-margin photos.</text>
  </grid-item>
  <grid-item>
    <AsyncImage query="Chilean rhubarb Gunnera tinctoria large invasive plant leaves New Zealand wetland" aspectRatio="5:4"/>
    **Chilean rhubarb**

    <text color="secondary" size="xs">Large, distinctive foliage. Potentially recognisable in wider landscape photographs.</text>
  </grid-item>
  <grid-item>
    <AsyncImage query="Cortaderia selloana invasive pampas grass New Zealand tall flowering plumes" aspectRatio="5:4"/>
    **Pampas grass**

    <text color="secondary" size="xs">Visible from a distance, but native toetoe is an important lookalike.</text>
  </grid-item>
  <grid-item>
    <AsyncImage query="wilding conifer pine young trees invading New Zealand high country grassland mountains" aspectRatio="5:4"/>
    **Wilding conifers**

    <text color="secondary" size="xs">Useful in landscape photographs, though planted trees must be distinguished from wildings.</text>
  </grid-item>
</grid>

DOC identifies these kinds of invasive plants as major ecological concerns. <Cite ref="turn690989search9"/>

For a Nelson/Tasman pilot, I'd start with old man's beard and a handful of other visually recognisable weeds, selected in consultation with local biosecurity specialists.

However, the most useful project might not focus on widespread weeds. It could focus on **finding the first evidence of a rare, high-impact invasive species entering a new geographic area.**

## 4. The biggest scientific challenges

**False positives are going to be the central problem.**

Suppose only one photograph in a thousand contains the particular invasive weed we're searching for. At 80% recall and a 1% false-positive rate, only about 7% of generated alerts would be genuine detections.

That makes independent validation, careful thresholds and human review essential.

Location adds another complication. An observation's GPS coordinates don't necessarily identify the precise location of a plant in the background. It might be on the other side of a river, or hundreds of metres away. Some iNaturalist coordinates are also intentionally obscured. <Cite ref="turn690989search0"/>

One especially interesting finding comes from a March 2026 study by the Canadian Food Inspection Agency. Researchers found that geographically restricted species-identification suggestions could miss invasive species that weren't expected to exist in that region. <Cite ref="turn490136view0"/>

That's important: **using existing distribution maps too aggressively can cause an early-detection system to miss exactly the unusual species it's designed to discover.**

Geographic plausibility should help prioritise reviews, not automatically veto visually credible detections.

## 5. Licensing matters

The photos aren't all unrestricted. Individual iNaturalist photographs have their own Creative Commons licences, frequently including non-commercial conditions.

More importantly, iNaturalist's published terms explicitly prohibit using its data to train AI models for commercial purposes. <Cite refs={["turn392704search5","turn392704search7"]}/>

Using already-trained models for inference is a different activity from training, but licensing and the intended use of the results still need checking. A commercial project should clarify permitted uses with iNaturalist.

There's also a practical community rule: only the original observer should create an iNaturalist observation from their encounter. An AI system should avoid automatically uploading someone else's photograph as a new observation. Instead, maintain candidate records separately and invite verification. <Cite ref="turn849963search3"/>

## 6. A genuinely worthwhile proof of concept

I'd run a retrospective study, rather than immediately launching a continuous monitoring service.

Take 20,000–50,000 suitably licensed historical New Zealand photographs, search for five priority weeds, and have knowledgeable reviewers evaluate the candidate detections.

The key questions would be whether the system can find genuine previously unrecorded occurrences, how accurately it identifies species, how much reviewer time each discovery requires, and whether the discoveries would have been useful at the time the photographs were taken.

The retrospective aspect is particularly attractive. Imagine discovering that a serious weed infestation was visible in a 2018 butterfly photograph, but the first conventional weed record for that locality wasn't until 2023.

That would provide unusually strong evidence of the value of secondary image analysis.

**My assessment:** the technical components are mature enough for an experimental system. The uncertainty is not whether AI can detect plants in images — it can — but whether enough incidental photographs contain identifiable, actionable weeds to justify the processing and review costs.

If the retrospective study demonstrates meaningful early detections, this could become a valuable extension of DOC's SWAT system, with applications to council biosecurity, restoration projects and conservation monitoring.

---

### **You** · Fri, 13 Nov, 6:56 pm

Where else can we get a bunch of photos that might contain plants, in NZ?

---

### **ChatGPT** · Fri, 13 Nov, 6:57 pm

<small><strong>Reasoning / progress:</strong><br>
I’ll focus on sources you can actually process at scale: geotagged ground-level photography, public image archives, and aerial imagery. I’ll separate technically accessible datasets from platforms whose licensing or API terms make bulk AI analysis difficult.</small>

There are several substantial sources of New Zealand photographs beyond iNaturalist, including one particularly interesting dataset from DOC: **more than 10 million wildlife camera-trap photographs, many of which contain vegetation that nobody has labelled.**

For AI-assisted weed detection, I'd prioritise ground-level imagery over conventional aerial photography, because you can often identify leaves, flowers, stems and climbing vines.

## Best sources to investigate

<box gap={3}>
  <row align="start" gap={3}>
    <AsyncImage query="New Zealand forest trail wildlife camera trap photograph vegetation trees undergrowth ground level" aspectRatio="4:5" maxWidth="122px"/>
    <box flex="1" gap={1}>
      <row align="center" wrap="wrap" gap={2}>
        **1. DOC wildlife camera-trap archive**
        <badge color="success">Top candidate</badge>
      </row>
      <text weight="medium">Approximately 10.1 million images</text>
      <text color="secondary" size="sm">3.3 million photographs containing animals, plus 6.8 million classified as empty.</text>
      DOC's cameras have photographed habitats throughout New Zealand. Vegetation is frequently visible behind the animals, and many cameras repeatedly photograph the same location.

      <text size="sm">The public LILA subset has 2.5 million images, accessible through cloud storage, with a permissive data licence. The larger DOC archive is hosted separately on S3. Location identifiers are provided, although precise geographic coordinates may require additional access.</text>
      <text size="sm"><Link url="https://lila.science/datasets/nz-trailcams" title="Explore dataset"/> <Cite refs={["turn193373search3","turn209126view0"]}/></text>
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <AsyncImage query="New Zealand Wellington Zealandia wildlife trail camera possum forest floor vegetation" aspectRatio="4:5" maxWidth="122px"/>
    <box flex="1" gap={1}>
      **2. Wellington camera-trap dataset**

      <text weight="medium">270,450 photographs from 187 locations</text>
      <text color="secondary" size="sm">An excellent smaller benchmark.</text>
      Contains wildlife images and empty frames, with CSV and COCO annotations. The dataset is approximately 185 GB and uses the permissive Community Data License Agreement.

      Because the cameras are fixed, you could compare photographs over time for changes in vegetation. Check for overlaps with the larger DOC collection before combining them.

      <text size="sm"><Link url="https://datasets.cms.waikato.ac.nz/taiao/wellington_camera_traps/" title="Explore dataset"/> <Cite ref="turn193373search4"/></text>
    </box>
  </row>
</box>

## More sources worth exploring

| Source | Scale and access | Best use |
|---|---|---|
| **<Entity category="software" value="Flickr" disambig="online photo sharing platform"/>** | Large worldwide archive; geospatial and licence filters through its API. API keys now require Pro. <Cite refs={["turn613185search3","turn613185search7"]}/> | Bushwalking, tourism, gardens and landscape photography |
| **<Entity category="organization" value="Wikimedia Commons"/>** | Freely licensed images with a geosearch API. <Cite ref="turn217247search18"/> | Historical and contemporary landscape photos |
| **<Entity category="organization" value="DigitalNZ"/>** | Metadata for 30M+ NZ digital items, including photographs, through an API. <Cite ref="turn721389search4"/> | Discovering photos held by museums, libraries and government agencies |
| **<Entity category="software" value="KartaView" disambig="open street-level imagery platform"/>** | Geotagged street-level photographs through a documented API. <Cite refs={["turn725218search6","turn721389search1"]}/> | Roadside invasive plants |
| **<Entity category="organization" value="GNS Science Visual Media Library"/>** | More than 200,000 landscape, geological and research images. Permissions vary. <Cite ref="turn721389search0"/> | Historic infestations visible in landscape photography |
| **<Entity category="organization" value="National Library of New Zealand"/>** | Approximately 1.6 million photographic archive items. Digitisation and rights vary. <Cite ref="turn725218search10"/> | Finding earlier evidence of invasive plant establishment |
| **<Entity category="organization" value="GBIF"/>** | Global biodiversity records, including images supplied by institutions other than iNaturalist. <Cite ref="turn613185search1"/> | Unrecognised weeds in animal and fungal observations |
| **<Entity category="organization" value="eBird Macaulay Library"/>** | Huge wildlife photo archive; research access can be requested. <Cite ref="turn671525search2"/> | Vegetation behind bird photographs |

The most relevant direct entry points are <Link url="https://www.flickr.com/services/api/" title="Flickr API"/>, <Link url="https://commons.wikimedia.org/wiki/Commons:Search_by_location" title="Wikimedia geosearch"/>, <Link url="https://digitalnz.org/developers" title="DigitalNZ API"/> and <Link url="https://kartaview.org/doc" title="KartaView API"/>.

## Don't overlook aerial imagery

<row align="start" gap={3}>
  <AsyncImage query="New Zealand aerial orthophoto farmland forest wilding pine vegetation landscape overhead" aspectRatio="4:5" maxWidth="132px"/>
  <box flex="1" gap={1}>
    **<Entity category="organization" value="Land Information New Zealand" /> (LINZ)**

    LINZ provides open aerial imagery covering approximately 95% of New Zealand, generally at 20–30 cm resolution in rural areas and 5–20 cm in urban areas.

    It is available as Cloud Optimised GeoTIFFs with STAC metadata in the public `s3://nz-imagery` bucket. Historical imagery also provides opportunities for change detection. <Cite refs={["turn725218search7","turn725218search16"]}/>

    <text size="sm"><Link url="https://registry.opendata.aws/nz-imagery/" title="AWS open imagery dataset"/></text>
  </box>
</row>

This is better suited to wilding conifers, gorse thickets, pampas and large vegetation patches than individual plants.

## Two institutional sources I'd approach directly

**NZTA road-survey video.** Waka Kotahi records network video during its annual SCRIM+ pavement surveys. That could be a particularly rich source of roadside vegetation images, but access to the footage would need to be negotiated. <Cite ref="turn193373search13"/>

**The National Vegetation Survey (NVS).** Manaaki Whenua maintains records from more than 120,000 vegetation survey plots, including historical photographs in its physical archive. Some datasets can be requested, potentially providing paired photographs and verified vegetation records. <Cite refs={["turn671525search0","turn671525search4"]}/>

## Where I'd start

For an actual pilot, I'd make three data streams:

1. **DOC camera traps:** detect understory plants in conservation areas, sampling a few daytime frames per camera per season rather than processing every near-duplicate.
2. **KartaView:** find invasive plants along roads and tracks, grouping photographs into geographic segments.
3. **LINZ aerial imagery:** identify likely infestations and changes in vegetation cover over time, then correlate with ground-level detections.

The resulting dataset could have a single geographic evidence model, recording the image source, date, approximate location, candidate species and image crop.

One particularly useful opportunity is to combine **historical Flickr and Wikimedia photographs with more recent street-level imagery** to reconstruct when a weed first became visible in an area.

For commercial deployment, the most straightforward starting points appear to be LINZ's openly licensed imagery and the permissively licensed DOC camera-trap dataset. For community photo platforms, you need to preserve image-specific attribution and respect their API and reuse terms. Google's Street View, in contrast, expressly prohibits bulk extraction and certain derived uses, so I wouldn't build a bulk-analysis pipeline around it. <Cite ref="turn721389search2"/>

**My first experiment would be 10,000 daytime DOC camera-trap photographs from one region, plus a matching roadside sample once a bounded check confirms KartaView's NZ coverage and terms.** That would give you a useful comparison between forest understory and roadside weed detection before committing to millions of images.

---

### **You** · Fri, 13 Nov, 7:48 pm

Why the fuck isn’t the “NZTA road-survey video” open data?

---

### **ChatGPT** · Fri, 13 Nov, 7:49 pm

<small><strong>Reasoning / progress:</strong><br>
I’ll check whether NZTA actually withholds the footage, or whether it’s simply unpublished. I’ll also look at the stated reasons, the contractor arrangements, and what the Official Information Act could get you.</small>

**Because NZTA appears to have treated the footage as an internal road-management asset rather than a public dataset. And there's a commercial subscription platform sitting between the public and the imagery.**

I found something particularly frustrating in NZTA's own documentation.

## The publicly funded footage is behind a subscription

NZTA's June 2025 guidance on its nationwide Consistent Condition Data Collection (CCDC) programme states:

- Road-survey video is uploaded to **Argonaut's Roadrunner platform**.
- Road controlling authorities (RCAs), such as councils, receive access to their footage free for six months.
- After that, they must arrange a subscription with Argonaut to continue accessing it. <Cite ref="turn982281view2"/>

NZTA also confirms that the programme is **100% funded through the National Land Transport Fund for 2024–27**. <Cite ref="turn587257search7"/>

This doesn't establish who owns the copyright or whether Argonaut has exclusive distribution rights. A hosting subscription can be separate from the underlying data rights.

But it does establish that publicly funded imagery is being distributed through a commercial access system rather than published as downloadable open data.

For context, the state-highway survey procurement awarded in September 2024 covers approximately **23,000 lane-kilometres**, including georeferenced road-corridor imaging. <Cite ref="turn982281view3"/>

And NZTA explicitly acknowledges that its SCRIM+ survey vehicles record forward-facing video of what drivers see along the highway. <Cite ref="turn587257search0"/>

That's potentially an extraordinary dataset for monitoring roadside weeds, slips, erosion, vegetation encroachment and changes in land use.

## This conflicts with New Zealand's open-data principles

The government's <Link url="https://www.data.govt.nz/toolkit/policies/new-zealand-data-and-information-management-principles" title="Data and Information Management Principles"/> say government-held information should generally be:

- Open and readily accessible unless legitimate grounds for restricting it exist.
- Free to use and reuse, with access charges discouraged.
- Released in machine-readable formats with metadata.
- Managed on behalf of the New Zealand public. <Cite ref="turn820812view1"/>

These principles aren't an absolute legal requirement to publish every dataset, but they establish a clear expectation.

I couldn't find a published NZTA explanation specifically justifying its decision not to release the survey videos as open data.

Possible reasons include privacy concerns over faces and number plates, existing commercial agreements, and the cost of preparing and distributing the footage. Those are plausible explanations, **not verified reasons NZTA has given**.

And none necessarily prevents releasing appropriately processed imagery.

## Here's the particularly interesting legal angle

There's an Ombudsman case almost directly on point.

In **case W43847 (2000)**, the Intellectual Property Office had outsourced document storage to a private company that charged people for access.

The agency tried to redirect an OIA requester to that commercial provider.

The Ombudsman found that information held by an independent contractor on behalf of a government agency is deemed to be held by the agency under section 2(5) of the Official Information Act. Referring the requester to the contractor wasn't sufficient grounds to refuse the request. <Cite ref="turn820812view0"/>

That doesn't automatically guarantee a complete copy of NZTA's imagery or an open reuse licence. But it means outsourcing storage does not, by itself, remove information from the OIA.

## What I'd challenge NZTA on

I'd submit an OIA request seeking the following:

1. The contractual clauses governing **ownership, copyright, licensing, export and public distribution** of the road-survey videos.
2. Any assessments or decisions concerning publication of those videos as open data.
3. An inventory of available survey videos, including geographic coverage, dates, formats and metadata.
4. Copies of a limited sample of 2025/26 footage and its geospatial metadata, preferably as downloadable files.

I'd also explicitly ask whether NZTA would consider publishing privacy-processed road-survey imagery under CC BY 4.0 for environmental monitoring, invasive-weed detection and research.

You can submit this through <Link url="https://nzta.govt.nz/about-us/our-data-and-official-information/official-information-act/making-an-official-information-act-request" title="NZTA's Official Information Act request page"/>.

**The bigger issue is procurement.** Public agencies should be ensuring that contracts for data collection preserve rights to publish the resulting data independently of the supplier's proprietary platform.

Otherwise, we can end up paying for a nationwide environmental imaging resource but being unable to exploit its considerable value outside its original road-engineering purpose.

The government policy already supports openness. The unanswered question is whether NZTA's commercial arrangements and operational decisions are preventing it.

---
