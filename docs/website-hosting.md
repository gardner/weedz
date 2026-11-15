# Website on beast

The review website is served at **https://weedz.llm.nz** through a dedicated
Cloudflare Tunnel. Next.js and the Python API run on beast, not Workers. This is
the user's 15 November deployment decision; the earlier vinext migration is deferred.
No paid-plan upgrade or existing tunnel/service change was made.

## Boundaries and active data

- Next production server: loopback 3058; `/api` is its same-origin authenticated proxy.
- Python API: loopback 8058, mandatory reviewer-token mode, no public API bind.
- Cloudflare ingress: `weedz.llm.nz` → `http://127.0.0.1:3058`, then terminal 404.
- Reviewer cookies are HttpOnly, Secure behind HTTPS and SameSite=Strict. Session,
  evidence, image and error responses carry `Cache-Control: private, no-store`.
- Hosted configuration must explicitly set `WEEDZ_API_URL`. An internal HTTP origin
  must be loopback; external origins require public HTTPS, without credentials/query.

The initial dataset is a fresh logical store of six source-licensed public photos
from `sam21-tiny-final` / `segmentation-experiment-v1`, with real saved SAM2.1 masks,
BioCLIP2 scores and model provenance. This is the measured class-agnostic proposal
experiment, not a claim of plant completeness or live inference. Coordinates,
capture/upload dates, source reviewer notes/history and credentials are not copied.
The source remains unchanged. New reviews belong to this independent hosted store.

The default run is now `licensed-plants-sam21-20261115`: nine curated licensed plant
photos (four source-labelled weed references and five lookalikes), with newly computed
SAM2.1/BioCLIP2 outputs. This is not representative or stratified sampling; generic
collection-query defaults do not describe the curated selection. The previous six-case
run and its review history remain available. The import adds a distinct run and image
namespace without replacing discovery history or reviewer credentials. Selection and
runtime provenance are retained in the owner’s plant experiment artifact directory.

There is no Temporal server/discovery worker in this service deployment. New collection
creation is explicitly disabled by `WEEDZ_RUN_CREATION=disabled` in both proxy and UI;
existing evidence, studies and review records remain usable. Enable collection creation
only after provisioning and verifying the workflow stack. No fake workflow response is used.
R2 is not part of the active storage path; durable data is on beast.

## Files and lifecycle

Owner-private data: `~/.local/share/weedz/site/data/`. Reviewer invites are separate
from discovery evidence in its `access.sqlite3`; plaintext owner invite delivery is
`~/.config/weedz/site/reviewer-token` (0600 inside a 0700 directory). Read that file locally
and paste it into the HTTPS sign-in form. Never put it in URLs, chat, screenshots or Git.
The tunnel connector credential is separately held at
`~/.config/weedz/cloudflare/site-tunnel-token`, also 0600. Administrative provisioning
credentials stay outside Git and are not needed by the running website.

Runtime code is an immutable release under `~/.local/share/weedz/site/releases/<commit>/`,
selected by `site/current`. The service uses a dedicated user-local Node 26 executable
at `site/runtime/node`. Build with
`NEXT_PUBLIC_WEEDZ_DEFAULT_RUN_ID=licensed-plants-sam21-20261115` to keep the curated
plant collection as the initial view while other runs are added. The value is public
build-time configuration, admitted only if that run actually exists and is completed;
otherwise the newest completed run is selected. User-selected runs stay selected during
refresh. Rebuild to change the preference. Runtime code must not depend on a removable development worktree or an
expiring tool session. User lingering was already enabled on beast.

The three templates in `deploy/systemd/` define only these new user units:

```sh
systemctl --user status weedz-site-api weedz-site-web weedz-site-tunnel
systemctl --user restart weedz-site-api weedz-site-web
journalctl --user -u weedz-site-api -u weedz-site-web -u weedz-site-tunnel
```

Do not restart or overwrite unrelated user services. Logs must never include invite
values or tunnel credentials. Use the reviewer CLI to revoke an invitation; removing
a browser cookie alone does not revoke it.

## Prepare another isolated data store

Run from a checked-out release with locked dependencies:

```sh
uv run --locked python scripts/seed_review_site.py \
  --source /absolute/licensed/experiment --run COMPLETED_RUN_ID \
  --output /absolute/NEW-private-data
```

This requires a new independent destination. It checks source checksums, decodes exactly
the verified bytes, makes metadata-free upright PNGs, retains original score/model
records, and starts with fresh review history. It never copies raw SQLite pages or
`access.sqlite3`. Serve using `scripts/serve_review_site.py --data PATH --port 8058`;
that entry point always requires tokens and binds 127.0.0.1. Create a fresh invite for
that store before giving anyone its URL. Keep data directories owner-only.

## Build, update and rollback

Keep a pinned release checkout/archive, run `uv sync --locked`, then in `web/` run
`pnpm install --frozen-lockfile`, `pnpm check`, and `pnpm build` using Node 26. Copy the
three service templates into the user's systemd directory only after verifying they
are this installation's units. Switch `site/current` to the new release, reload user
systemd and restart the API/web units. Keep the previous release for rollback; switch
the symlink back and restart those two units. The data directory and tunnel credential
stay outside releases and must not be overwritten during an update.

Before declaring an update healthy, verify anonymous evidence returns 401, valid HTTPS sign-in,
Secure/HttpOnly/Strict cookie, real PNG bytes/MIME, private no-store headers, actual
mask→original toggling, disabled unavailable collection creation, and sign-out→401.
A source-only build is not proof of a functioning public route. Browser interaction,
review writes and token revocation need their own verification; screenshots alone do
not prove them. Cloudflare bot policy may refuse non-browser clients; normal HTTPS
browser behavior is the user-facing acceptance target.
