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
Device commissioning, onboarding portal and user database sync. Image: `ghcr.io/hevea-project/{arch}-gateway` (built by the hevea mono-repo CI). Source: `../docker/gateway/`

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
# Access Point and OpenVPN use the default image template
python3 sync_addons.py ../hassio-access-point ../hassio-openvpn

# Gateway is synced from the hevea mono-repo with a target name override
# and a custom image template (images are named {arch}-gateway by the CI)
python3 sync_addons.py ../docker/gateway:hassio-gateway \
  --image-template "ghcr.io/hevea-project/{arch}-{addon}"
```

The script:
- Finds `config.yaml` (handles nested paths)
- Strips Supervisor-only fields (`startup`, `boot`)
- Sets `slug` to directory name (or target name with `path:target` syntax), `image` from `--image-template` using the **source** directory name (default `ghcr.io/hevea-project/<dir>`, override with e.g. `--image-template "ghcr.io/hevea-project/{arch}-{addon}"`)
- Filters `arch` to supported platforms
- Maps mono-repo add-on slugs to apps-repo directory names (`hevea_hassio_gateway` → `hassio-gateway`, etc.) in `app_name`, `openvpn_app_name`, `ap_app_name` options
- Sets `app_name` to match the target slug (the gateway uses it as its own add-on slug for Supervisor API calls)
- Copies or generates `DOCS.md`

The gateway is synced from the mono-repo with a target name override:
`../docker/gateway:hassio-gateway` syncs into `hassio-gateway/` (the source
directory is named `gateway` but the app must be `hassio-gateway`). The image
template must be `ghcr.io/hevea-project/{arch}-{addon}` because the CI names
images `{arch}-{service}` (e.g. `amd64-gateway`), and the `{addon}` placeholder
is replaced with the **source** directory name (`gateway`), not the target name.

## Key Patterns

- No Dockerfiles in this repo — images are built in sibling repos
- `slug` must match the directory name for Home Assistant to locate the image
- `logo.svg` is an inline SVG (800x800, 80px rounded rect background)
- `DOCS.md` uses Markdown with `# Home Assistant App:` heading convention
