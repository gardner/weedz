# Reviewed datasets and reproducible releases

Externally labelled datasets remain upstream source evidence. They are useful for
pipeline evaluation without being represented as Weedz expert-reviewed NZ gold.
The first NZ cohort can be prepared for review now; publishing it as gold requires
completed human reviews and the explicitly chosen review policy below.

## Capture existing reviews without changing the source

```sh
uv run main.py release review-snapshot \
  --source /absolute/path/to/existing/discovery-run-root \
  --run actual-run-id --namespace stable-store-namespace \
  --output-dir /absolute/outside-git/new-review-snapshot
```

This opens the existing SQLite database read-only and captures photos, model metadata,
findings, suggestion reviews, identity/location/history/novelty judgements, audits,
referrals and follow-up selections in one transaction. Every event keeps its source
row, timestamp, actual actor and common snapshot hash. Later withdrawals supersede
that actor's preceding decision; superseded events remain in the manifest. Missing
legacy actor attribution stays explicitly unattributed source evidence.

Use one stable namespace for a database across exports. Namespaced source reviewer
names identify recorded accounts; they do not certify botanical expertise. The source
must have pinned media hashes. This snapshot is an inference-only historical export,
with original media references, rather than a self-contained gold release.

Namespaces use 1–100 ASCII letters, digits, dots, underscores or hyphens, starting
with a letter or digit. Colons are reserved identity delimiters. Actual source
reviewer names retain their original colons and Unicode characters; only the
operator-supplied namespace is restricted. Keep older snapshots unchanged.

Known iNaturalist observer logins use `inaturalist:login:<login>`, with the original login
also retained in context. The observation group is preserved. An encounter group is
added only when the existing grouping rule has sufficient date, observer and public
coordinate evidence. An encounter is not a verified site. Obscured positions have
unknown uncertainty; missing site/observer evidence is never filled with fake groups.

## Bring completed Label Studio annotations back

Use the completed-human importer and its opt-in configuration. Imported drafts,
predictions and model-evidence text do not become human annotations. Completed human
declarations preserve actual creator/editor identities and revision history, but do
not by themselves establish expertise, independent review or gold eligibility.

A single completed Label Studio submission declares its own completeness. Its editor
is the author of that declaration, so it cannot satisfy independent review of
completeness merely because the annotation's original creator was someone else. Use an
explicit non-independent policy for that workflow, or record a separate, attributable
review before requiring independence. The offline end-to-end fixture uses the former
and is never represented as independently reviewed NZ data.

The importer produces `samples.jsonl` and pinned local images/masks. Keep raw exports
and configuration snapshots private. A frozen release carries canonical history and
their hashes; it does not publish arbitrary private export files.

## Choose the review and split policy explicitly

A detection release spec can contain:

```json
{
  "name": "nz-reviewed-v1",
  "task": "detection",
  "protocol": "Expert-checked visible target plants; site/observer-disjoint splits.",
  "split": {
    "kind": "explicit",
    "group_key": "site",
    "assignment": {
      "actual-fit-site": "fit",
      "actual-validation-site": "validation",
      "actual-test-site": "test"
    }
  },
  "test_status": "fresh",
  "rights_profile": "noncommercial-cc0-by-nc",
  "review_policy": {
    "taxa": ["Ulex europaeus"],
    "min_reviewers": 1,
    "independent": true,
    "required_groups": ["site", "observer"]
  }
}
```

The site names above are placeholders. Supply actual grouping evidence and actual
reviewer requirements; add `reviewer_ids` to restrict acceptance to the programme's
approved account roster. No default number of experts or expertise is invented.
Every qualifying non-model label needs accepted reviewer evidence and matching active
acceptance history. Independent review excludes the claim's author. Conflicting,
withdrawn or reopened decisions cannot satisfy the policy.

Each photo also needs accepted whole-image detection completeness covering every named
target. A checked zero-box photo is a scoped negative, without a fictitious absent box.
No annotation, a model suggestion being accepted, a rejected suggestion, or an audit
answer alone establishes exhaustive completeness. Source labels remain usable under
the general contract while failing this stricter gold policy.

## Freeze and verify the complete release

```sh
uv run main.py release freeze \
  --manifest /absolute/reviewed-package/samples.jsonl \
  --manifest-sha256 ACTUAL_SHA256 \
  --spec /absolute/release-spec.json \
  --assets-root /absolute/reviewed-package \
  --output-dir /absolute/outside-git/new-release
uv run main.py release verify /absolute/outside-git/new-release
```

The writer checks the manifest checksum, validates policy/rights and whole-group splits,
then captures exact images, standing masks, supported historical review masks and any
declared sparse-assessment mask. Every reference needs its SHA-256 and a confined
relative path. The writer stages and syncs all files before one directory rename, so
interruption cannot expose a manifest without its release record or assets. Reading
the release checks record, manifest and referenced asset hashes again.

Gold writes require `--assets-root`. Legacy releases without materialized assets retain
their existing format and identity. New contract features use schema 2; existing plain
schema-1 manifest bytes and release IDs remain unchanged. Record test inspection or
model selection with `release status`; an inspected test never becomes fresh again.

## Noncommercial source rights

Batch and experiment exporters accept `--rights-profile noncommercial-cc0-by-nc` as an
explicit opt-in. Canonical Temporal requests must carry the same `rights_profile`, and
their pinned `ready.json` must bind it too. Packaging, publication and subsequent human
imports preserve that profile. Both image and metadata licences are checked, retained
verbatim and displayed in the visible source credit. A generic `cc-by-nc` code is not
silently assigned a licence version.

The default remains `public-cc0-by`, and its optional field is omitted so existing
public identities remain unchanged. A noncommercial profile cannot adopt an existing
public readiness grant or package, substitute for contributed-image consent, or admit
custom publisher terms as if they were Creative Commons licences. CWFID's custom
research terms therefore need a separate private research workflow.

Direct targeted review events must retain the contemporaneous full claim snapshot
in `payload.claim`. Identity, geometry, taxon/category scope, authorship and derivation
must match the standing claim. Only `review` and `reviewers` are excluded from the
content comparison: these describe vote state, so a conflicting rejection or reopening
of the same claim still vetoes acceptance. Completed human revisions use their existing
full supported claim snapshots. Historical pilot events without a claim snapshot remain
faithfully preserved inference evidence; IDs alone do not establish gold acceptance.
The exporter never invents a snapshot for an existing real historical decision.

Release publication keeps staging owner-private until every file has been written
and synced. A new legacy format-1 release retains normal mkdir/umask permissions;
a new format-2/history-bearing release or review snapshot defaults to0700. To
explicitly share one, pre-create an empty output directory with the intended mode,
group and ACL. Publication preserves those directory attributes when atomically
replacing it. Destination group/default ACL inheritance is initialized before
writing children, while access to staging remains owner-only. File permissions
still follow the caller's umask or that explicit default ACL; arrange an appropriate
umask for readers of the files as well. The human-import package always remains
owner-private and is not affected by release-sharing choices.
