# pg-provision

[![PyPI - Version](https://img.shields.io/pypi/v/pg-provision.svg)](https://pypi.org/project/pg-provision/) [![Python Versions](https://img.shields.io/pypi/pyversions/pg-provision.svg)](https://pypi.org/project/pg-provision/)

Idempotent PostgreSQL provisioning as a Python package wrapping portable shell scripts.

## Install

```
pip install pg-provision
```

## Quick start

Show usage (pass‑through to shell script):

```bash
pgprovision --help
```

Dry run (no privileged operations):

```bash
pgprovision --dry-run
```

> Root or passwordless sudo is required for changes. The CLI auto‑invokes `sudo -n` when needed.

User mode (no sudo) uses `postgres`, `initdb`, `pg_ctl`, and `psql` binaries already available to the invoking user and matching `PG_VERSION`:

```bash
pgprovision --user-mode \
  --pg-bin-dir /path/to/postgresql/bin \
  --user-base-dir "$HOME/.local/share/pgprovision/pg16" \
  --data-dir "$HOME/.local/share/pgprovision/pg16/data" \
  --port 55432
```

Equivalent env knobs: `PGPROVISION_MODE=user` or `USER_MODE=true`, `PG_BIN_DIR`, `PGPROVISION_USER_BASE_DIR`, and `PGPROVISION_USER_RUNTIME_DIR`. In user mode the default repo is `none`; `--repo pgdg|os` fails because package/repo management needs system privileges. TLS reuses `server.crt`/`server.key` already placed in PGDATA, `pg_stat_statements`/`pgvector` require matching control files under the resolved PostgreSQL `share/extension`, and logical destroy uses the user runtime `psql` path. `--unix-socket-group` never creates groups or changes membership; the group must already exist and include the current user. `--local-map-entry` writes `pg_ident.conf`, but mapped OS users must already be able to access the user socket.

User mode can also bootstrap PostgreSQL from a trusted local or remote tarball. The tarball must contain one common root with `bin/postgres`, `bin/initdb`, `bin/pg_ctl`, and `bin/psql`; all four binaries must be executable and match `PG_VERSION`. A SHA256 digest is mandatory for every tarball, including local files; pg-provision does not trust unsigned or unchecked binaries.

```bash
pgprovision --user-mode \
  --bootstrap-tarball /path/to/postgresql.tar.gz \
  --bootstrap-sha256 "<sha256>" \
  --bootstrap-only
```

Equivalent env knobs: `PGPROVISION_BOOTSTRAP_TARBALL`, `PGPROVISION_BOOTSTRAP_SHA256`, `PGPROVISION_BOOTSTRAP_DIR` (default: `$PGPROVISION_USER_BASE_DIR/binaries`), and `BOOTSTRAP_ONLY=true`.

PostgreSQL 16 remains the default for this release. PostgreSQL 18 is explicitly supported through PGDG by passing `--pg-version 18` or setting `PG_VERSION=18` in an env file:

```bash
pgprovision --pg-version 18 --dry-run
```

## Contributing

Use [uv](https://docs.astral.sh/uv/) for the contributor environment. The end-user install path remains `pip install pg-provision`.

```bash
uv sync --dev
uv run pytest -q
bash -n src/pgprovision/_sh/provision.sh src/pgprovision/_sh/os/*.sh
uv run pre-commit run --all-files
uv build
```

Install hooks with `uv run pre-commit install`. During development, run the CLI through the project environment:

```bash
uv run pgprovision --dry-run
uv run pgprovision --user-mode --dry-run
```

## Common scenarios (copy/paste)

### 1) **Hardened (RHEL/Rocky/Alma): socket‑only, local peer auth**

No TCP listener; UNIX socket is gated by a dedicated group; OS users are mapped to DB roles via `pg_ident`. Good default for single‑host services.

```bash
pgprovision \
  --repo pgdg \
  --listen-addresses '' \
  --socket-only \
  --unix-socket-group pgclients \
  --unix-socket-permissions 0770 \
  --local-peer-map localmap \
  --local-map-entry alice:app_rw \
  --local-map-entry bob:analytics \
  --admin-group-role dba_group \
  --admin-dbrole dba
```

**Notes**

- `--listen-addresses ''` disables TCP; only UNIX sockets are used.
- `--unix-socket-group` controls who can connect locally; members are added automatically.
- `--local-map-entry OSUSER:DBROLE` writes `pg_ident.conf` and ensures DB roles exist.
- Optional safety switch once your admin path works:

```bash
pgprovision --disable-postgres-login
```

______________________________________________________________________

### 2) **Hardened (RHEL/Rocky/Alma): loopback‑only TCP (localhost)**

Keep TCP on `127.0.0.1`/`::1` only; pair with peer mappings (for local tooling) or layer your own auth later.

```bash
pgprovision \
  --repo pgdg \
  --listen-addresses localhost \
  --port 5432 \
  --local-peer-map localmap \
  --local-map-entry serviceuser:service_role
```

______________________________________________________________________

### 3) **Permissive (Ubuntu): listen on all interfaces for a trusted LAN**

Opens the server to a private IPv4 range (add IPv6 if needed). This example **does not** create credentials; bring your own auth model.

```bash
pgprovision \
  --repo pgdg \
  --listen-addresses '*' \
  --allowed-cidr 192.168.0.0/16 \
  --allow-network
```

Add IPv6:

```bash
pgprovision \
  --repo pgdg \
  --listen-addresses '*' \
  --allowed-cidr 192.168.0.0/16 \
  --allowed-cidr-v6 'fd00::/8' \
  --allow-network
```

> Network exposure without an explicit auth strategy is risky. Use this only on trusted networks and add your own authentication/authorization controls.

______________________________________________________________________

### 4) **TLS‑required server (certs pre‑positioned)**

Enables TLS. The script fails early if `server.crt`/`server.key` are absent in the active `data_directory`.

```bash
pgprovision \
  --repo pgdg \
  --listen-addresses '*' \
  --allowed-cidr 10.0.0.0/8 \
  --allow-network \
  --enable-tls
```

______________________________________________________________________

### 5) **Reproducible runs via env‑file (no secrets)**

Keep knobs in a file. Any flag‑backed var can live here.

`/etc/pgprovision.env`:

```bash
PG_VERSION=16  # set PG_VERSION=18 to target PostgreSQL 18 via PGDG
REPO_KIND=pgdg
LISTEN_ADDRESSES=localhost
PORT=5432
ALLOW_NETWORK=false
```

Run:

```bash
pgprovision --env-file /etc/pgprovision.env
```

(You can still pass additional flags on the command line for things like peer mappings.)

______________________________________________________________________

### 6) **Custom data directory + pg_stat_statements**

```bash
pgprovision \
  --repo pgdg \
  --pg-version 18 \
  --data-dir /data/postgres/18/main \
  --init-pg-stat-statements
```

When requested, the script preloads `pg_stat_statements`, restarts PostgreSQL, and runs `CREATE EXTENSION IF NOT EXISTS pg_stat_statements;`.

______________________________________________________________________

### 7) **pgvector on PGDG PostgreSQL**

pgvector is opt-in and does not use `shared_preload_libraries`.

```bash
pgprovision \
  --repo pgdg \
  --pg-version 18 \
  --create-db appdb \
  --init-pgvector \
  --pgvector-db appdb
```

The provisioner installs the PGDG pgvector package for the selected major and runs `CREATE EXTENSION IF NOT EXISTS vector;` in the target database.

______________________________________________________________________

### 8) **Logical destroy: drop one database and optional role**

Logical destroy only runs SQL against a reachable cluster. It does not remove packages, services, PGDATA, or cluster metadata. Non-dry-runs require exact database-name confirmation.

```bash
pgprovision --destroy-db old_app --dry-run
sudo pgprovision --destroy-db old_app --destroy-user old_app \
  --confirm-destroy-db old_app --destroy-only
```

Protected targets such as `postgres`, `template0`, `template1`, `pg_*`, and configured admin roles are refused.

______________________________________________________________________

### 9) **Cluster uninstall: remove service metadata, PGDATA, and packages**

Cluster uninstall is separate from logical destroy and always starts with a dry-run manifest. The manifest prints `confirm_token=...`; use that exact token for any non-dry-run.

```bash
pgprovision --pg-version 16 --uninstall-cluster --uninstall-only --dry-run \
  | tee ./pgprov-uninstall-preview.log
TOKEN="$(sed -n 's/^confirm_token=//p' ./pgprov-uninstall-preview.log | tail -n1)"
test -n "$TOKEN"
```

Preserve PGDATA while deregistering/stopping the system cluster:

```bash
sudo pgprovision --pg-version 16 \
  --uninstall-cluster --uninstall-only \
  --confirm-uninstall "$TOKEN"
```

Full system teardown, including PGDATA and versioned packages (optionally the PGDG repo):

```bash
sudo pgprovision --pg-version 16 \
  --uninstall-cluster --uninstall-only \
  --remove-pgdata --purge-packages --remove-pgdg-repo \
  --confirm-uninstall "$TOKEN"
```

User-mode uninstall only removes user-owned paths; pass the same user-mode paths used for provision:

```bash
pgprovision --user-mode --pg-bin-dir /path/to/postgresql/bin \
  --user-base-dir "$HOME/.local/share/pgprovision/pg16" \
  --data-dir "$HOME/.local/share/pgprovision/pg16/data" \
  --uninstall-cluster --uninstall-only --dry-run \
  | tee ./pgprov-user-uninstall-preview.log
TOKEN="$(sed -n 's/^confirm_token=//p' ./pgprov-user-uninstall-preview.log | tail -n1)"
pgprovision --user-mode --pg-bin-dir /path/to/postgresql/bin \
  --user-base-dir "$HOME/.local/share/pgprovision/pg16" \
  --data-dir "$HOME/.local/share/pgprovision/pg16/data" \
  --uninstall-cluster --uninstall-only --remove-pgdata \
  --confirm-uninstall "$TOKEN"
```

______________________________________________________________________

## OS Guides

- Ubuntu: [docs/test-plan-ubuntu.md](docs/test-plan-ubuntu.md)
- RHEL/Rocky/Alma: [docs/test-plan-rhel.md](docs/test-plan-rhel.md)

### Self‑Heal on Ubuntu (PGDG)

On Ubuntu/Debian with PGDG, packaging normally creates a default `main` cluster. If that metadata is broken (e.g., `pg_lsclusters` errors, `/etc/postgresql/<ver>/main` owned by root, or `data_directory` missing), pg‑provision can self‑heal before applying HBA/profile/role changes.

- Non‑destructive: it never deletes a directory that looks like a real PGDATA (has `PG_VERSION` and `global/pg_control`).
- If a valid PGDATA exists, it rebuilds Debian metadata to point at it (adoption), then starts the service.
- Default behavior is on; disable with `--no-self-heal` or `SELF_HEAL=false`.
- See `docs/test-plan-ubuntu.md` for self‑heal scenarios.

### Self‑Heal on RHEL (PGDG)

On RHEL family (RHEL/Rocky/Alma/Fedora/Amazon Linux), the provisioner preflights the cluster and will adopt an existing valid `PGDATA` by setting a systemd override (`Environment=PGDATA=…`) and ensuring permissions/SELinux context. If no valid data exists, it initializes a fresh cluster using packaging helpers (`postgresql-setup`) or `initdb`.

- Non‑destructive: never deletes a directory that looks like a real PGDATA.
- See `docs/test-plan-rhel.md` for self‑heal scenarios.

## CI and release gates

| Job                              | Coverage                                                                         | Gates publish? |
| -------------------------------- | -------------------------------------------------------------------------------- | -------------- |
| `pre-commit`                     | Repository hygiene hooks                                                         | Yes            |
| `unit`                           | Python matrix plus packaged shell artifact and CLI dry-run checks                | Yes            |
| `fedora-smoke`                   | Fedora 42 container dry-run smoke                                                | Yes            |
| `build`                          | sdist/wheel build, install, and CLI dry-run smoke                                | Yes            |
| `integration-ubuntu-smoke`       | Ubuntu PGDG provision, `SHOW server_version`, logical destroy, uninstall dry-run | No             |
| `user-mode-smoke`                | Ubuntu user-mode provision/stamp/destroy and uninstall dry-run                   | No             |
| `integration-ubuntu-destructive` | Nightly/manual preserve-PGDATA and full package/PGDATA uninstall for PG 16/18    | No             |
| RHEL full integration            | Manual/self-hosted runner until RHEL-like systemd/PGDG coverage is stable        | No             |

Tag publishes require `pre-commit`, `unit`, `fedora-smoke`, and `build`. Ubuntu integration and full RHEL integration remain schedule/manual coverage and do not block release publication.

## Notes

- Linux-only. Commands that modify the system require root or passwordless sudo.
- See the test guides for end-to-end provisioning scenarios.

### Secrets

For non-interactive provisioning without leaking passwords, prefer a file-based secret and avoid passing passwords on the command line:

```
CREATE_PASSWORD_FILE=/run/secrets/pgpass \
pgprovision --create-user app --create-db app
```

This prevents secrets from appearing in argv or logs.

## Project Links

- PyPI: https://pypi.org/project/pg-provision/
- Release 0.2.5: https://pypi.org/project/pg-provision/0.2.5/
