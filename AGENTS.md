# AGENTS.md

This document provides essential context for agents working with the **hevea-hassio-apps** repository.

## Project Overview

Home Assistant Apps repository containing three apps for the Hevea project. Each app is a container image referenced from GHCR (`ghcr.io/hevea-project/<app>` by default; see `--image-template` in `sync_addons.py`). Dockerfiles live in the sibling addon repositories (`../hassio-access-point/`, `../hassio-openvpn/`) and in the hevea mono-repo (`../docker/gateway/`).

## Structure

```
repository.yaml           # Repository metadata (name, url, maintainer)
README.md                 # User-facing documentation
sync_addons.py            # Script to sync configs/docs from source repos
hassio-access-point/
  config.yaml             # App configuration (name, slug, arch, options, schema, image)
  DOCS.md                 # User documentation
  logo.svg                # App icon
hassio-openvpn/
  config.yaml
  DOCS.md
  logo.svg
hassio-gateway/
  config.yaml
  DOCS.md
  logo.svg
```

## App Details

### hassio-access-point
Creates a WiFi access point on the Home Assistant host using hostapd/dnsmasq. Supports SSID config, DHCP, MAC filtering, and client internet routing. Source: `../hassio-access-point/hassio-access-point/`

### hassio-openvpn
Connects the Home Assistant host to a remote network via OpenVPN. Requires tun device and NET_ADMIN capability. Maps addon config, backup, and share directories. Source: `../hassio-openvpn/`

### hassio-gateway
Device commissioning, onboarding portal and user database sync. Image: `ghcr.io/hevea-project/gateway` (multi-arch manifest built by the hevea mono-repo CI). Source: `../docker/gateway/`

## Configuration Format

All `config.yaml` files follow the Home Assistant Apps format:
- `name`, `version`, `slug` (must match directory name), `description`
- `arch`: `[aarch64, amd64]`
- `image`: set by `sync_addons.py` from `--image-template` (default `ghcr.io/hevea-project/<dir>`)
- `options` / `schema`: input validation and defaults
- Optional: `privileged`, `devices`, `host_network`, `host_dbus`, `hassio_api`, `hassio_role`, `webui`, `map`

## Syncing

To sync configs and docs from source addon repositories:

```bash
python3 sync_addons.py ../hassio-access-point ../hassio-openvpn ../docker/gateway:hassio-gateway
```

The script:
- Finds `config.yaml` (handles nested paths)
- Strips Supervisor-only fields (`startup`, `boot`)
- Sets `slug` to directory name (or target name with `path:target` syntax), `image` from `--image-template` using the **source** directory name (default `ghcr.io/hevea-project/<dir>`)
- Filters `arch` to supported platforms
- Maps mono-repo add-on slugs to apps-repo directory names (`hevea_hassio_gateway` → `hassio-gateway`, etc.) in `app_name`, `openvpn_app_name`, `ap_app_name` options
- Sets `app_name` to match the target slug (the gateway uses it as its own add-on slug for Supervisor API calls)
- Copies or generates `DOCS.md`

The gateway is synced from the mono-repo with a target name override:
`../docker/gateway:hassio-gateway` syncs into `hassio-gateway/` (the source
directory is named `gateway` but the app must be `hassio-gateway`).
The image resolves to `ghcr.io/hevea-project/gateway` via the multi-arch
manifest published by the mono-repo CI (which also publishes per-arch
images as `amd64-gateway`, `aarch64-gateway`).

## Versioning and Releases

Home Assistant uses the `version` field from `config.yaml` as the Docker image tag:
`version: "1.2.3"` → HA pulls `ghcr.io/hevea-project/gateway:1.2.3`.

The mono-repo CI publishes images with tags derived from git tags (`v1.2.3` → `1.2.3`).
To release a new version:

1. Update `version` in `../docker/gateway/config.yaml` (mono-repo)
2. Commit, push to master, and create a git tag `v1.2.3`
3. CI publishes `ghcr.io/hevea-project/gateway:1.2.3`
4. Sync this repo: `python3 sync_addons.py ../docker/gateway:hassio-gateway`
5. Commit and push — Home Assistant detects the new version

The `version` in `config.yaml` must match a published image tag on GHCR.

## Key Patterns

- No Dockerfiles in this repo — images are built in sibling repos
- `slug` must match the directory name for Home Assistant to locate the image
- `logo.svg` is an inline SVG (800x800, 80px rounded rect background)
- `DOCS.md` uses Markdown with `# Home Assistant App:` heading convention
