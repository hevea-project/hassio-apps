# Home Assistant App: Hevea Gateway

Hevea Gateway: device commissioning, onboarding portal and user database sync.

## Home Assistant authentication (Hevea users)

The gateway links Hevea users to Home Assistant: a user can log into Home
Assistant with their Hevea email and password.

Using the `homeassistant_config:rw` map, the gateway installs in the Home
Assistant configuration directory:

- `hevea-auth.py`: a shim executed by Home Assistant's `command_line` auth
  provider (inside the HA container, on the host network) with the login
  credentials in the environment. It POSTs them to the gateway's
  `/api/v1/auth/validate` endpoint.
- an `auth_providers` entry in `configuration.yaml`:

  ```yaml
  homeassistant:
    auth_providers:
      - type: command_line
        command: /config/hevea-auth.py
        meta: true
  ```

The gateway adds the entry automatically (idempotent) and restarts Home
Assistant Core once when the configuration changes, because auth providers
are loaded only at startup. If another `command_line` provider is already
configured, the gateway leaves it alone (Home Assistant rejects duplicate
providers of the same type).

Credential validation goes through the app API when it is reachable. When
the app is unreachable, the gateway falls back to the user database synced
from the app (`sync_enabled`, `sync_db_path`, `db.json`), so Home Assistant
logins keep working offline. For the fallback to work, the sync must have
run at least once.

Groups: the site owner (Hevea role `admin`) gets the Home Assistant
`system-admin` group, other members get `system-users`. Service accounts
never get a Home Assistant account.

On the first Home Assistant login with a Hevea account, Home Assistant
creates the user automatically (the username is the Hevea email address).
