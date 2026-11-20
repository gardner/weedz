# Great Walks · Fungi seasons

A distinct, non-commercial research project inside this repository. It does not
call Weedz identification models or change the weed-review application.

The repeatable pipeline downloads photographic iNaturalist fungi observations,
joins them to sourced DOC route corridors, calculates seasonal recording patterns,
and builds a **single self-contained interactive HTML file**. It works offline
when copied to another computer and needs no server, external scripts or tiles.

## Current delivered snapshot

- All **11 Great Walks**, including Whanganui Journey, clearly labelled as paddling.
- Observation dates **2016–2025**, ten complete calendar years.
- Public/open coordinates, known accuracy at most **1,000 metres**, within **10 km**
  of each original sourced route in **NZTM2000 / EPSG:2193**.
- **10,636 distinct eligible observation IDs** across the union of those areas.
  One record can contribute to more than one nearby walk; summing walk totals
  therefore does not yield the unique union total.
- Research-grade and needs-identification records with photographs. All Fungi,
  including lichens; no claim that records depict fruiting mushrooms.
- Month counts, tied recorded peaks, unique observer-days, sample size and year
  coverage are visible. These are recording patterns, not fungal abundance,
  guaranteed photographic conditions or safe hiking-season recommendations.

Current artifact on beast:

```text
/home/gardner/src/great-walks-fungi/site/index.html
```

The entire `site/` directory contains only aggregate counts, route/coastline
geometry and build evidence. Individual observation coordinates, observer IDs
and downloaded replies remain in the owner-private snapshot directory outside Git.

## Reproduce or refresh

Use Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js and pnpm:

```sh
cd projects/great-walks-fungi
uv sync --locked
pnpm --dir web install --frozen-lockfile
uv run python -m pipeline.run --data-root /absolute/path/to/fungi-data
```

From an empty data root this acquires GIS source data and observations. Existing
checksummed replies are reused; interrupted acquisitions resume without starting
over. Orphan cache data/receipts are refetched; a corrupt completed reply fails
closed. No photographs or thumbnails are downloaded.

The default snapshot is `snapshot-v1`. Rerunning it reuses its source replies,
recomputes geographic admission and summaries, and rebuilds the HTML. To fetch
fresh observation replies into a new dated snapshot:

```sh
uv run python -m pipeline.run --data-root /absolute/path/to/fungi-data --refresh
```

GIS source selections are frozen under `raw/gis-extra/` and checksum-verified.
A new data root reacquires those sources, including current source membership;
it fails if selected DOC segments have disappeared rather than inventing geometry.
Changing observation years or buffer size also requires a new snapshot:

```sh
uv run python -m pipeline.run --data-root /absolute/path/to/fungi-data \
  --snapshot corridor-5km-2020-2025 --first-year 2020 --last-year 2025 --radius-km 5
```

To rebuild viewing output without network requests:

```sh
uv run python -m pipeline.run --data-root /absolute/path/to/fungi-data --render-only
```

The static export is always `DATA_ROOT/site/index.html`. Summary JSON and a
build receipt containing source-code/output hashes are emitted alongside it.
`--render-only` accepts `--snapshot NAME` for an earlier snapshot. A final build
requires all eleven walks; a partial acquisition is not presented as complete.

## Pipeline and evidence

1. `sources.py` queries official DOC source segments and Natural Earth. Stable DOC
   functional-location selectors are tracked in `pipeline/gis-sources.json`.
2. `catalog.py` selects the eight exact walking-experience routes and adopts
   explicit source segments for Heaphy, Milford and Whanganui.
3. `download.py` calculates a metric route buffer and its acquisition bounding
   box. iNaturalist requests use ascending observation IDs, at most approximately
   one per second, retries/backoff and a checksummed raw-response cache.
4. `analysis.py` excludes unsuitable dates, private/obscured coordinates, unknown
   or excessive coordinate uncertainty and points outside the actual corridor.
   Counts use observation dates, not upload dates, and deduplicate observation IDs.
5. `render.py` emits only aggregates and sourced map geometry. Viewing route lines
   are simplified by 60 metres; **analysis uses the original geometry**, so a
   display line is not a second spatial-admission rule or navigation route.
6. `web/check-browser.mjs` verifies all eleven walk selections, monthly filtering,
   zoom/reset, layout overflow and visible coastline. It runs with browser network
   access disabled and captures desktop/mobile screenshots for visual inspection.

Raw replies retain source licences, request parameters, retrieval times and SHA256
receipts. The final source cache and per-walk snapshots are private; only the
aggregate standalone map is appropriate for serving publicly. The iNaturalist
search link shows the acquisition rectangle and will include records excluded by
our stricter final route/privacy/accuracy filters; it is not an identical count.

DOC geometry is retained without connecting missing parts. Heaphy/Milford source
segment lengths differ from advertised walking distances. Whanganui's two source
parts have a roughly 24-metre gap. The broad ecological corridor accommodates this;
none of these geometries or lengths is offered for navigation.

## Interpretation

Counts depend on visitor numbers, access, weather, photographer effort, uneven
coverage and identification practices. More records can mean more photographers,
not more fungi. Unknown accuracy/privacy exclusions can change which places are
represented. Observer-days are an effort diagnostic, not a complete correction.
Small samples are flagged using an explicit display heuristic of fewer than 30
records or fewer than three represented years. Ties remain tied, and cross-season
ties use a neutral map marker rather than selecting one winning season.

Check current DOC guidance independently. The map does not establish edibility,
absence, fruiting dates or current track safety. Fungi identification is community
metadata, not independent expert verification commissioned by this project.

## Validation

```sh
uv run python -m unittest discover -s tests -v
node web/check-browser.mjs /absolute/path/to/fungi-data
```

Browser binaries must already be available to Playwright. The delivered run was
checked with existing local Chromium; no system browser installation was needed.
Screenshots and browser receipts are in `DATA_ROOT/qa/`. Raw data and generated
artifacts do not belong in Git. Source code, dependency locks and source-selection
specifications are versioned here.

## Sources and rights

- [DOC walking experiences](https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_Walking_Experiences/FeatureServer)
- [DOC infrastructure tracks](https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_Tracks_Open_Data/FeatureServer/0)
- [DOC Whanganui journey](https://services1.arcgis.com/3JjYDyG3oajxU6HO/arcgis/rest/services/DOC_WhanganuiJourneyLine_DTO/FeatureServer/0)
- [iNaturalist API](https://api.inaturalist.org/v1/docs/) and its contributors;
  original observation/photo licences remain separate. Photo bytes are not reused.
- [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/), public domain.

DOC/Crown source metadata supplies CC BY terms; metadata and source selections
are preserved with the GIS evidence. No third-party mirror is used in the final
route bundle. Dependencies retain their own licences. The optional isolated CVAT
path deployment is documented in [deploy/README.md](deploy/README.md).
