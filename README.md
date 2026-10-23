# Hevea Apps

Home Assistant Apps (formerly add-ons) for the Hevea project.

## Apps

| App | Description |
| --- | --- |
| [hassio-access-point](hassio-access-point/) | Create a WiFi access point to directly connect devices to Home Assistant |
| [hassio-openvpn](hassio-openvpn/) | Connect Home Assistant to a remote network via OpenVPN |
| [hassio-gateway](hassio-gateway/) | Device commissioning, onboarding portal and user database sync |

## Installation

Add this repository to your Home Assistant Supervisor store:

1. Open **Supervisor** → **Store**
2. Click the **⋮** menu → **Repositories**
3. Add: `https://github.com/hevea-project/hassio-apps`
4. Click **Save**

Or use the button below:

[![Add Repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhevea-project%2Fhassio-apps)

## Syncing

To sync configs and docs from the source addon repositories:

```bash
# Access Point and OpenVPN use the default image template
python3 sync_addons.py ../hassio-access-point ../hassio-openvpn

# Gateway is synced from the hevea mono-repo with a target name override
# and a custom image template (images are named {arch}-gateway by the CI)
python3 sync_addons.py ../docker/gateway:hassio-gateway \
  --image-template "ghcr.io/hevea-project/{arch}-{addon}"
```

## License

See individual app directories for license information.
