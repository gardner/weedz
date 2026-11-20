# Optional static publication beside CVAT

The downloadable HTML is the primary portable output. On beast, an independent
rootless container can also serve it at <https://cvat.llm.nz/map/>. It does not
install code into CVAT or publish observation records as annotation tasks.

The supplied user service joins the existing `weedz-cvat` Podman network. The
existing Traefik Docker provider discovers its labels. A higher-priority router
matches only `/map` and `/map/…`; CVAT pages and `/api/` retain their own routers.
No CVAT restart or tunnel/DNS change is needed. The Python image is pinned by
digest and was already cached on this machine. The container has a read-only
filesystem and mount, no Linux capabilities and no exposed host port.

## Install on the existing beast deployment

After building and inspecting the final HTML, copy **only public output files** to
`~/.local/share/great-walks-fungi/public/map/`. Never mount the raw-data directory,
repository, credentials, or private per-observation exports as the document root.
Use an atomic rename for `index.html` so refreshes do not serve a partial file.

Copy `great-walks-fungi-map.service` to `~/.config/systemd/user/`, then:

```sh
systemctl --user daemon-reload
systemctl --user enable --now great-walks-fungi-map.service
```

The configured network and image digest are deployment-specific. On another host,
select the intended network and verify/pull the pinned image before enabling.
This service relies on the existing CVAT proxy and Cloudflare tunnel staying up.

## Verify and remove

Check `/map/` over public HTTPS, exercise selection controls in a browser, and
retain screenshots. Also check that CVAT's `/` and `/api/server/about` still
return successfully. A successful service start alone does not verify the map.
The pipeline is an explicit refresh command; this service does not periodically
fetch data or execute the analysis.

To remove this optional publication, disable and stop only
`great-walks-fungi-map.service`. The map router then disappears automatically.
The local downloadable artifact and pipeline remain usable.
