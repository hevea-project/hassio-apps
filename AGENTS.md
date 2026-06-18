# AGENTS.md

This document provides essential context for agents working with the **hevea-hassio-apps** repository.

## Project Overview

Home Assistant Apps repository containing three apps for the Hevea project. Each app is a container image referenced from Docker Hub (`docker.io/lebauce/hevea`). Dockerfiles live in the sibling addon repositories (`../hassio-access-point/`, `../hassio-openvpn/`, `../hassio-onboarding/`).

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
hassio-onboarding/
  config.yaml
  DOCS.md
  logo.svg
```

## App Details

### hassio-access-point
Creates a WiFi access point on the Home Assistant host using hostapd/dnsmasq. Supports SSID config, DHCP, MAC filtering, and client internet routing. Source: `../hassio-access-point/hassio-access-point/`

### hassio-openvpn
Connects the Home Assistant host to a remote network via OpenVPN. Requires tun device and NET_ADMIN capability. Maps addon config, backup, and share directories. Source: `../hassio-openvpn/`

### hassio-onboarding
Interactive captive portal for onboarding new Home Assistant users. Guides WiFi setup, VPN credential retrieval, and service activation via the Supervisor API. Source: `../hassio-onboarding/`

## Configuration Format

All `config.yaml` files follow the Home Assistant Apps format:
- `name`, `version`, `slug` (must match directory name), `description`
- `arch`: `[aarch64, amd64]`
- `image`: `docker.io/lebauce/hevea:<slug>`
- `options` / `schema`: input validation and defaults
- Optional: `privileged`, `devices`, `host_network`, `host_dbus`, `hassio_api`, `hassio_role`, `webui`, `map`

## Syncing

To sync configs and docs from source addon repositories:

```bash
python3 sync_addons.py ../hassio-access-point ../hassio-openvpn ../hassio-onboarding
```

The script:
- Finds `config.yaml` (handles nested paths)
- Strips Supervisor-only fields (`startup`, `boot`)
- Sets `slug` to directory name, `image` to `docker.io/lebauce/hevea:<dir>`
- Filters `arch` to supported platforms
- Copies or generates `DOCS.md`

## Key Patterns

- No Dockerfiles in this repo — images are built in sibling repos
- `slug` must match the directory name for Home Assistant to locate the image
- `logo.svg` is an inline SVG (800x800, 80px rounded rect background)
- `DOCS.md` uses Markdown with `# Home Assistant App:` heading convention
