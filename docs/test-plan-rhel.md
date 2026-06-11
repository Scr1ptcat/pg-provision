# PostgreSQL Provisioner – RHEL/Rocky/Alma Test Guide (pgprovision)

This guide validates the **pg-provision** package on RHEL 8/9 (and Rocky/Alma). It assumes PGDG is used by default for system-mode package provisioning. It covers installation, service health, user-mode operation, HBA policy, profiles, users/DBs, TLS, relocation, and SELinux/firewalld nuances.

______________________________________________________________________

## 0) Prerequisites

- RHEL 8/9, Rocky 8/9, or Alma 8/9 VM with internet access.
- Willingness to install PostgreSQL via PGDG. The default major is 16; set `PGV=18` to run the same guide against PostgreSQL 18.
- Install uv and the pg-provision tool in the shell that will invoke `pgprovision`:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  uv tool install pg-provision
  pgprovision --help
  ```
  Upgrade with `uv tool upgrade pg-provision`.

**Recommended shell setup**

```bash
set -euxo pipefail
export PGV="${PGV:-16}"
```

For system-mode sections, run as root or as a user with passwordless sudo. If you switch to a root shell for the guide, install `pgprovision` with uv in that same shell first. Run user-mode sections as the unprivileged user that should own the PostgreSQL data directory.

> If non-root, ensure passwordless sudo and that helpers writing under `$PGDATA` and `/var/lib/pgsql/...` use sudo.
> **Important — CLI behavior:** `pgprovision` prints usage and exits if called with **no arguments**. Environment variables alone do **not** trigger execution. Include at least one flag. This guide uses **CLI flags that mirror defaults** (e.g., `--pg-version "${PGV}"`) to match `provision.sh` with no args.

**CLI ⇄ Env quick map**

- `--socket-only` ⇄ `SOCKET_ONLY=true`
- `--allow-network` ⇄ `ALLOW_NETWORK=true`
- `--allowed-cidr` / `--allowed-cidr-v6` ⇄ `ALLOWED_CIDR` / `ALLOWED_CIDR_V6`
- `--profile NAME` ⇄ `PROFILE=NAME`
- `--enable-tls` ⇄ `ENABLE_TLS=true`
- `--data-dir PATH|auto` ⇄ `DATA_DIR=...`
- `--create-user/--create-db/--create-password` ⇄ `CREATE_USER/CREATE_DB/CREATE_PASSWORD` (prefer `CREATE_PASSWORD_FILE` for secrets)
- `--user-mode` ⇄ `PGPROVISION_MODE=user` or `USER_MODE=true`
- `--pg-bin-dir` / `--user-base-dir` / `--user-runtime-dir` ⇄ `PG_BIN_DIR` / `PGPROVISION_USER_BASE_DIR` / `PGPROVISION_USER_RUNTIME_DIR`
- `--bootstrap-tarball` / `--bootstrap-sha256` / `--bootstrap-only` ⇄ `PGPROVISION_BOOTSTRAP_TARBALL` / `PGPROVISION_BOOTSTRAP_SHA256` / `BOOTSTRAP_ONLY=true`
- `--destroy-db/--destroy-user/--destroy-only` ⇄ `DESTROY_DB/DESTROY_USER/DESTROY_ONLY`; confirmation uses `PGPROVISION_CONFIRM_DESTROY_DB`
- `--uninstall-cluster/--uninstall-only/--confirm-uninstall` ⇄ `UNINSTALL_CLUSTER/UNINSTALL_ONLY/PGPROVISION_CONFIRM_UNINSTALL`
- `--remove-pgdata/--purge-packages/--remove-pgdg-repo` ⇄ `REMOVE_PGDATA/PURGE_PACKAGES/REMOVE_PGDG_REPO`

______________________________________________________________________

## 1) Dry‑run smoke test

```bash
pgprovision --dry-run | tee ./pgprov_dryrun_rhel.log
# Assert: dry-run must not try to install packages
! grep -qE '(^|[[:space:]])(dnf|yum)[[:space:]]+install([[:space:]]|$)' ./pgprov_dryrun_rhel.log
```

______________________________________________________________________

## 1.5) User-mode smoke (no sudo)

User mode uses PostgreSQL binaries already available to the invoking user and keeps PGDATA under a user-owned directory. It does not install packages, create system users/groups, or prepare PGDG/AppStream repositories. On Fedora/RHEL-family hosts with distro PostgreSQL packages available, install binaries separately and pass their directory explicitly:

```bash
sudo dnf -y install postgresql-server postgresql || sudo yum -y install postgresql-server postgresql
PG_MAJOR="$(psql --version | awk '{print $3}' | cut -d. -f1)"
PG_BIN_DIR="$(dirname "$(command -v psql)")"
BASE="$HOME/.local/share/pgprovision/rhel-user-smoke"
SOCKET_GROUP="$(id -gn)"
rm -rf "$BASE"

pgprovision --user-mode --pg-version "$PG_MAJOR" \
  --pg-bin-dir "$PG_BIN_DIR" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none --unix-socket-group "$SOCKET_GROUP" \
  --create-db pgprov_user_smoke

test -f "$BASE/data/.pgprovision_provisioned.json"

pgprovision --user-mode --pg-version "$PG_MAJOR" \
  --pg-bin-dir "$PG_BIN_DIR" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none --unix-socket-group "$SOCKET_GROUP" \
  --destroy-db pgprov_user_smoke --dry-run

pgprovision --user-mode --pg-version "$PG_MAJOR" \
  --pg-bin-dir "$PG_BIN_DIR" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none --unix-socket-group "$SOCKET_GROUP" \
  --destroy-db pgprov_user_smoke \
  --confirm-destroy-db pgprov_user_smoke --destroy-only

pgprovision --user-mode --pg-version "$PG_MAJOR" \
  --pg-bin-dir "$PG_BIN_DIR" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none --unix-socket-group "$SOCKET_GROUP" \
  --uninstall-cluster --uninstall-only --dry-run
```

### Optional: tarball bootstrap

For environments without preinstalled PostgreSQL server packages, provide a trusted PostgreSQL tarball. The tarball must have a single common root containing executable `bin/postgres`, `bin/initdb`, `bin/pg_ctl`, and `bin/psql`; the SHA256 digest is mandatory for local and remote tarballs.

```bash
TARBALL="/path/to/postgresql.tar.gz"
SHA256="<sha256>"
BASE="$HOME/.local/share/pgprovision/rhel-user-tarball"

pgprovision --user-mode \
  --bootstrap-tarball "$TARBALL" \
  --bootstrap-sha256 "$SHA256" \
  --user-base-dir "$BASE" \
  --bootstrap-only

pgprovision --user-mode --pg-version "$PGV" \
  --bootstrap-tarball "$TARBALL" \
  --bootstrap-sha256 "$SHA256" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none
```

______________________________________________________________________

## 2) Full install (PGDG repo, packages, cluster, service)

The provisioner should:

- Install PGDG repo RPM.
- Disable the AppStream PostgreSQL module.
- Install `postgresql${PGV}`, `postgresql${PGV}-server`, and `postgresql${PGV}-contrib`.
- Initialize and start the service.

Run (include a neutral default flag to trigger execution):

```bash
pgprovision --pg-version "${PGV}" | tee ./pgprov_install_rhel.log

systemctl status "postgresql-${PGV}" --no-pager || true
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SELECT version();"
```

**If service didn’t start:**

```bash
systemctl status "postgresql-${PGV}" --no-pager -l || true
journalctl -xeu "postgresql-${PGV}" --no-pager | tail -n 100 || true
# Initialize cluster manually if needed:
sudo "/usr/pgsql-${PGV}/bin/postgresql-${PGV}-setup" initdb || true
systemctl enable --now "postgresql-${PGV}" || true
```

**Paths (PGDG on RHEL)**

- Data dir: `/var/lib/pgsql/${PGV}/data`
- Configs: `/var/lib/pgsql/${PGV}/data/postgresql.conf` (plus `pg_hba.conf`, `pg_ident.conf`)
- Service: `postgresql-${PGV}`

______________________________________________________________________

## 3) HBA policy

```bash
HBA="/var/lib/pgsql/${PGV}/data/pg_hba.conf"
awk '/^# pgprovision:hba begin \(managed\)/,/^# pgprovision:hba end/' "$HBA"
```

### Socket‑only posture

```bash
pgprovision --socket-only
awk '/^# pgprovision:hba begin \(managed\)/,/^# pgprovision:hba end/' "$HBA" | grep -A2 'socket-only'
```

### Allow networks

```bash
pgprovision --allow-network --allowed-cidr "10.0.0.0/8, 192.168.1.0/24"
awk '/^# pgprovision:hba begin \(managed\)/,/^# pgprovision:hba end/' "$HBA" | grep -E '10\.0\.0\.0/8|192\.168\.1\.0/24'
```

> **Note:** Even with HBA allowing remote connections, firewalld/SELinux may still block. See Troubleshooting.

______________________________________________________________________

## 4) Profiles (conf.d drop‑in)

Your provisioner adds `include_dir = 'conf.d'` and writes a drop‑in in the same directory as `postgresql.conf`.

```bash
mkdir -p profiles
cat >profiles/xl-32c-256g.conf <<'EOF'
shared_buffers=64GB
effective_cache_size=192GB
work_mem=32MB
maintenance_work_mem=2GB
wal_buffers=16MB
max_wal_size=32GB
checkpoint_completion_target=0.9
default_statistics_target=250
track_io_timing=on
EOF

pgprovision --profile xl-32c-256g
DROPIN="/var/lib/pgsql/${PGV}/data/conf.d/99-pgprovision.conf"
grep -E 'shared_buffers|max_wal_size|track_io_timing' "$DROPIN"
```

______________________________________________________________________

## 5) User and database creation

```bash
pgprovision --create-user devuser --create-password 'pAs$123' --create-db devdb

sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname='devuser';"
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE datname='devdb';"
```

______________________________________________________________________

## 5.5) Logical destroy safety smoke

Drops only logical objects on a running cluster; it does not remove PGDATA, packages, services, or cluster metadata. Confirmation must exactly match the final `DESTROY_DB`.

```bash
DB=pgprov_destroy_smoke
ROLE=pgprov_destroy_smoke
PSQL="$(command -v psql || echo /usr/pgsql-${PGV}/bin/psql)"
PASSFILE=$(mktemp)
trap 'rm -f "$PASSFILE"' EXIT
printf '%s\n' 'not-secret-for-disposable-test' > "$PASSFILE"
sudo -n env CREATE_PASSWORD_FILE="$PASSFILE" pgprovision \
  --create-db "$DB" --create-user "$ROLE"
pgprovision --destroy-db "$DB" --dry-run
set +e
pgprovision --destroy-db "$DB" --destroy-only
echo "unconfirmed destroy RC=$?"
set -e
PGPROVISION_CONFIRM_DESTROY_DB="$DB" \
  pgprovision --destroy-db "$DB" --destroy-user "$ROLE" --destroy-only
sudo -u postgres "$PSQL" -XAt -c "SELECT 1 FROM pg_database WHERE datname='${DB}'" | grep -q '^1$' && exit 1 || true
```

______________________________________________________________________

## 6) Socket group & local peer map

```bash
ME=$(logname 2>/dev/null || echo "$SUDO_USER")
pgprovision --local-peer-map localmap --local-map-entry "${ME}:dev_role" --unix-socket-group pgclients

getent group pgclients
getent group pgclients | grep -E "(^|,|\\s)${ME}(\\s|,|$)" || true
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SELECT rolname FROM pg_roles WHERE rolname = 'dev_role';"
```

______________________________________________________________________

## 6.5) pgvector extension (PGDG)

```bash
DB=pgprov_vector_smoke
pgprovision --pg-version "${PGV}" --repo pgdg \
  --create-db "$DB" \
  --init-pgvector --pgvector-db "$DB"
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -XAt -d "$DB" -c "SELECT extname FROM pg_extension WHERE extname='vector';" | grep '^vector$'
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -XAt -c "SHOW shared_preload_libraries;" | grep -v vector
```

**Expect:** `vector` exists in the target database, and `shared_preload_libraries` does not include `vector`. AppStream/OS repository pgvector packages are not assumed; use `--repo pgdg` for this smoke.

______________________________________________________________________

## 7) TLS guardrail and enablement

### 7.1 Guardrail

```bash
set +e
pgprovision --enable-tls
echo "RC=$?"
set -e
```

### 7.2 Self-signed certs and TLS enablement

```bash
DATA_DIR="/var/lib/pgsql/${PGV}/data"
install -o postgres -g postgres -m 0700 -d "$DATA_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$DATA_DIR/server.key" -out "$DATA_DIR/server.crt" -subj "/CN=localhost" -days 365
chown postgres:postgres "$DATA_DIR/server.crt" "$DATA_DIR/server.key"
chmod 0600 "$DATA_DIR/server.key"

pgprovision --enable-tls
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SHOW ssl;"
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SHOW ssl_min_protocol_version;"
```

______________________________________________________________________

## 8) Custom data directory relocation (SELinux aware)

> Destructive to the default cluster.

```bash
NEW_DATA="/var/lib/pgsql/${PGV}/custom-data"
pgprovision --data-dir "$NEW_DATA"
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SHOW data_directory;" | grep -F "$NEW_DATA"
```

**If SELinux blocks startup**, label and restore contexts:

```bash
# install semanage if needed
dnf -y install policycoreutils-python-utils || yum -y install policycoreutils-python

semanage fcontext -a -t postgresql_db_t "${NEW_DATA}(/.*)?"
restorecon -Rv "${NEW_DATA}"

systemctl restart "postgresql-${PGV}"
systemctl is-active --quiet "postgresql-${PGV}" && echo "service up"
```

______________________________________________________________________

## 9) Stamp file & permissions

```bash
STAMP="${NEW_DATA:-/var/lib/pgsql/${PGV}/data}/.pgprovision_provisioned.json"
ls -l "$STAMP"
cat "$STAMP"
```

______________________________________________________________________

## 10) Restart sanity

```bash
systemctl restart "postgresql-${PGV}"
systemctl is-active --quiet "postgresql-${PGV}" && echo "service up"
sudo -u postgres "/usr/pgsql-${PGV}/bin/psql" -At -c "SELECT 1;"
```

______________________________________________________________________

## Troubleshooting

- **Service didn’t start**:

  ```bash
  systemctl status "postgresql-${PGV}" --no-pager -l
  journalctl -xeu "postgresql-${PGV}" --no-pager | tail -n 100
  ```

______________________________________________________________________

## 11) Self-heal: missing/invalid PGDATA (fresh create)

```bash
set -euxo pipefail
PGV=16
# Detect service name (PGDG vs AppStream)
if systemctl list-unit-files --type=service | grep -q "^postgresql-${PGV}\.service"; then
  SVC="postgresql-${PGV}"
else
  SVC="postgresql"
fi

# Simulate missing data dir
systemctl stop "$SVC" 2>/dev/null || true
rm -rf "/var/lib/pgsql/${PGV}/data"

# Provisioner should create and start cleanly
pgprovision --pg-version "${PGV}"
systemctl is-active --quiet "$SVC"
# Pick psql path gracefully
PSQL="$(command -v psql || echo /usr/pgsql-${PGV}/bin/psql)"
sudo -u postgres "$PSQL" -At -c "SELECT 1;"
```

______________________________________________________________________

## 12) Self-heal: adopt existing valid PGDATA

```bash
set -euxo pipefail
PGV=16
# Detect service name (PGDG vs AppStream)
if systemctl list-unit-files --type=service | grep -q "^postgresql-${PGV}\.service"; then
  SVC="postgresql-${PGV}"
else
  SVC="postgresql"
fi
REAL_DATA="/var/lib/pgsql/${PGV}/adopt-me"

# Prepare a valid PGDATA manually
install -o postgres -g postgres -m 0700 -d "$REAL_DATA"
INITDB="$(command -v initdb || echo /usr/pgsql-${PGV}/bin/initdb)"
sudo -u postgres "$INITDB" -D "$REAL_DATA"

# Remove any override so the service points to default initially
rm -f "/etc/systemd/system/${SVC}.service.d/override.conf"
systemctl daemon-reload || true

# Run provisioner; expect adoption (override to REAL_DATA, service up)
pgprovision --pg-version "${PGV}"
systemctl is-active --quiet "$SVC"
PSQL="$(command -v psql || echo /usr/pgsql-${PGV}/bin/psql)"
sudo -u postgres "$PSQL" -At -c "SHOW data_directory;" | grep -Fx "$REAL_DATA"
```

- **SELinux AVC denials** (custom data dir):

  ```bash
  getenforce
  ausearch -m AVC -ts recent || true
  # fix contexts:
  semanage fcontext -a -t postgresql_db_t "/path/to/data(/.*)?"
  restorecon -Rv /path/to/data
  systemctl restart "postgresql-${PGV}"
  ```

- **firewalld blocks remote connections** (if you allowed networks in HBA):

  ```bash
  firewall-cmd --add-service=postgresql --permanent
  firewall-cmd --reload
  # or:
  firewall-cmd --add-port=5432/tcp --permanent && firewall-cmd --reload
  ```

- **Permission denied writing under `$PGDATA`**: run as root or ensure helpers use sudo for writes under `/var/lib/pgsql/${PGV}/data`.

______________________________________________________________________

## Cleanup (optional)

Scripted uninstall is the primary cleanup path. Always preview first and extract the `confirm_token=` from the dry-run output. Re-run the preview if you change `PGV`, `--data-dir`, or any env file that affects the resolved target. RHEL-family PGDG installs do not provide an Ubuntu-style `pg_lsclusters` preview source, and default stamp files under `/var/lib/pgsql/` are postgres-owned; use `sudo` for default cleanup previews, or pass an explicit `--data-dir` when previewing without sudo.

### Preserve PGDATA, remove service metadata

```bash
PREVIEW_LOG=./pgprov_uninstall_preview_rhel.log
sudo pgprovision --pg-version "${PGV}" \
  --uninstall-cluster --uninstall-only --dry-run | tee "$PREVIEW_LOG"
TOKEN="$(sed -n 's/^confirm_token=//p' "$PREVIEW_LOG" | tail -n1)"
test -n "$TOKEN"

sudo pgprovision --pg-version "${PGV}" \
  --uninstall-cluster --uninstall-only \
  --confirm-uninstall "$TOKEN"
```

### Full teardown, including PGDATA and packages

```bash
PREVIEW_LOG=./pgprov_uninstall_full_preview_rhel.log
sudo pgprovision --pg-version "${PGV}" \
  --uninstall-cluster --uninstall-only --dry-run | tee "$PREVIEW_LOG"
TOKEN="$(sed -n 's/^confirm_token=//p' "$PREVIEW_LOG" | tail -n1)"
test -n "$TOKEN"

sudo pgprovision --pg-version "${PGV}" \
  --uninstall-cluster --uninstall-only \
  --remove-pgdata --purge-packages --remove-pgdg-repo \
  --confirm-uninstall "$TOKEN"
```

Manual dnf/yum cleanup is secondary, for recovery when the scripted path cannot run:

```bash
systemctl stop "postgresql-${PGV}" || systemctl stop postgresql || true
rm -f "/etc/systemd/system/postgresql-${PGV}.service.d/override.conf"
systemctl daemon-reload || true
dnf -y remove "postgresql${PGV}"\* "pgvector_${PGV}" pgdg-redhat-repo || \
  yum -y remove "postgresql${PGV}"\* "pgvector_${PGV}" pgdg-redhat-repo || true
rm -rf "/var/lib/pgsql/${PGV}" /etc/yum.repos.d/pgdg-redhat-all.repo /var/log/pgsql
groupdel pgclients || true
```

______________________________________________________________________

**End of guides.**
