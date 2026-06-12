import textwrap

import pytest


def _make_valid_pgdata(path, major="16"):
    (path / "global").mkdir(parents=True)
    (path / "base").mkdir()
    (path / "pg_wal").mkdir()
    (path / "global" / "pg_control").write_bytes(b"x")
    (path / "PG_VERSION").write_text(f"{major}\n", encoding="utf-8")
    path.chmod(0o700)


@pytest.mark.unit
def test_uninstall_requires_uninstall_only(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      RUNTIME_REQUESTED_MODE=system
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      UNINSTALL_CLUSTER=true
      UNINSTALL_ONLY=false
      DRY_RUN=false
      validate_uninstall_request
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 2
    assert "requires --uninstall-only" in r.stderr
    assert "Refusing to combine uninstall and provision" in r.stderr


@pytest.mark.unit
def test_uninstall_dry_run_prints_manifest_and_token(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      os_detect() { OS_FAMILY=ubuntu; }
      load_os_module() {
        os_stop_cluster() { echo "mutating stop"; return 99; }
        os_uninstall_cluster() { echo "mutating uninstall"; return 99; }
        os_purge_packages() { echo "mutating purge"; return 99; }
        os_cleanup_repo() { echo "mutating repo"; return 99; }
      }
      pg_lsclusters() {
        printf '16 main 5432 down postgres %s log\\n' "${DATA:?}"
      }
      main --uninstall-cluster --uninstall-only --pg-version 16 --dry-run
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 0, r.stderr
    assert "Cluster uninstall manifest" in r.stdout
    assert f"data_dir: {data}" in r.stdout
    assert f"confirm_token=uninstall:16:ubuntu:{data}" in r.stdout
    assert "mutating " not in r.stdout


@pytest.mark.unit
def test_uninstall_requires_matching_confirmation(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      RUNTIME_REQUESTED_MODE=system
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      UNINSTALL_CLUSTER=true
      UNINSTALL_ONLY=true
      DRY_RUN=false
      PGPROVISION_CONFIRM_UNINSTALL=wrong-token
      validate_uninstall_request
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 2
    assert "Uninstall confirmation mismatch" in r.stderr
    assert f"Expected confirmation: uninstall:16:ubuntu:{data}" in r.stderr
    assert "Provided confirmation: wrong-token" in r.stderr


@pytest.mark.unit
def test_uninstall_confirmation_validated_after_env_file(tmp_path, bash):
    cli_data = tmp_path / "cli-data"
    env_data = tmp_path / "env-data"
    _make_valid_pgdata(cli_data)
    _make_valid_pgdata(env_data)
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text(f"DATA_DIR={env_data}\n", encoding="utf-8")

    r = bash(
        """
      parse_args --uninstall-cluster --uninstall-only --pg-version 16 \
        --confirm-uninstall "uninstall:16:ubuntu:${CLI_DATA:?}" \
        --data-dir "${CLI_DATA:?}" --env-file "${ENVF:?}"
      load_env_file
      OS_FAMILY=ubuntu
      RUNTIME_REQUESTED_MODE=system
      DRY_RUN=false
      resolve_uninstall_target
      validate_uninstall_request
        """,
        env={"CLI_DATA": str(cli_data), "ENVF": str(env_file)},
    )

    assert r.rc == 2
    assert f"Expected confirmation: uninstall:16:ubuntu:{env_data}" in r.stderr
    assert f"Provided confirmation: uninstall:16:ubuntu:{cli_data}" in r.stderr


@pytest.mark.unit
def test_remove_pgdg_repo_requires_purge_packages(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      RUNTIME_REQUESTED_MODE=system
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      UNINSTALL_CLUSTER=true
      UNINSTALL_ONLY=true
      REMOVE_PGDG_REPO=true
      PURGE_PACKAGES=false
      DRY_RUN=true
      validate_uninstall_request
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 2
    assert "--remove-pgdg-repo requires --purge-packages" in r.stderr


@pytest.mark.unit
def test_remove_pgdg_repo_rejected_in_user_mode(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=user
      RUNTIME_REQUESTED_MODE=user
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      UNINSTALL_CLUSTER=true
      UNINSTALL_ONLY=true
      REMOVE_PGDG_REPO=true
      PURGE_PACKAGES=true
      DRY_RUN=true
      validate_uninstall_request
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 2
    assert "--remove-pgdg-repo is system-mode only" in r.stderr


@pytest.mark.unit
def test_remove_pgdata_yes_env_file_triggers_pgdata_removal(tmp_path, bash):
    data = tmp_path / "pgdata"
    env_file = tmp_path / "pgprovision.env"
    _make_valid_pgdata(data)
    env_file.write_text("REMOVE_PGDATA=yes\n", encoding="utf-8")

    r = bash(
        """
      os_detect() { OS_FAMILY=ubuntu; }
      load_os_module() {
        os_stop_cluster() { return 0; }
        os_uninstall_cluster() {
          printf 'backend_remove_pgdata=%s\\n' "${REMOVE_PGDATA:-unset}"
          [[ "${REMOVE_PGDATA:-false}" == "true" ]] || return 8
          printf 'pg_dropcluster --stop %s main\\n' "$PG_VERSION"
          rm -rf -- "${DATA_DIR:?}"
        }
        os_purge_packages() { return 0; }
        os_cleanup_repo() { return 0; }
      }
      main --pg-version 16 --data-dir "${DATA:?}" \
        --env-file "${ENVF:?}" \
        --uninstall-cluster --uninstall-only \
        --confirm-uninstall "uninstall:16:ubuntu:${DATA:?}"
        """,
        env={"DATA": str(data), "ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr
    assert "remove_pgdata: true" in r.stdout
    assert "backend_remove_pgdata=true" in r.stdout
    assert "pg_dropcluster --stop 16 main" in r.stdout
    assert not data.exists()


@pytest.mark.unit
def test_uninstall_target_discovery_order(tmp_path, bash):
    explicit = tmp_path / "explicit"
    discovered = tmp_path / "discovered"
    stamped = tmp_path / "stamped"
    for path in [explicit, discovered, stamped]:
        _make_valid_pgdata(path)
    (stamped / ".pgprovision_provisioned.json").write_text("{}\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${EXPLICIT:?}"
      pg_lsclusters() {
        printf '16 main 5432 down postgres %s log\\n' "${DISCOVERED:?}"
      }
      _uninstall_stamp_roots() { printf '%s\\n' "${STAMPED:?}"; }
      resolve_uninstall_target
      printf 'DATA_DIR=%s\\nSOURCE=%s\\n' "$DATA_DIR" "$UNINSTALL_TARGET_SOURCE"
        """,
        env={
            "EXPLICIT": str(explicit),
            "DISCOVERED": str(discovered),
            "STAMPED": str(stamped),
        },
    )

    assert r.rc == 0, r.stderr
    assert f"DATA_DIR={explicit}" in r.stdout
    assert "SOURCE=explicit-data-dir" in r.stdout


@pytest.mark.unit
def test_uninstall_target_multiple_candidates_fails(tmp_path, bash):
    discovered = tmp_path / "discovered"
    stamped = tmp_path / "stamped"
    _make_valid_pgdata(discovered)
    _make_valid_pgdata(stamped)
    (stamped / ".pgprovision_provisioned.json").write_text("{}\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR=auto
      pg_lsclusters() {
        printf '16 main 5432 down postgres %s log\\n' "${DISCOVERED:?}"
      }
      _uninstall_stamp_roots() { printf '%s\\n' "${STAMPED:?}"; }
      resolve_uninstall_target
        """,
        env={"DISCOVERED": str(discovered), "STAMPED": str(stamped)},
    )

    assert r.rc == 2
    assert "Multiple uninstall targets resolved" in r.stderr
    assert str(discovered) in r.stderr
    assert str(stamped) in r.stderr


@pytest.mark.unit
def test_ubuntu_preserve_pgdata_quarantines_config_without_pg_dropcluster(
    tmp_path, bash
):
    data = tmp_path / "pgdata"
    etcdir = tmp_path / "etc-postgresql" / "16" / "main"
    quarantine = tmp_path / "quarantine"
    _make_valid_pgdata(data)
    etcdir.mkdir(parents=True)
    (etcdir / "postgresql.conf").write_text("data_directory = 'x'\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      SUDO=()
      PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR="${ETCDIR:?}"
      PGPROVISION_UBUNTU_QUARANTINE_ROOT="${QUARANTINE:?}"
      load_os_module
      pg_lsclusters() {
        [[ -d "${PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR}" ]] &&
          printf '16 main 5432 down postgres %s log\\n' "$DATA_DIR"
      }
      pg_dropcluster() { echo "pg_dropcluster called"; return 99; }
      os_uninstall_cluster
      [[ ! -d "${ETCDIR:?}" ]]
      find "${QUARANTINE:?}" -mindepth 1 -maxdepth 1 -type d -print
        """,
        env={"DATA": str(data), "ETCDIR": str(etcdir), "QUARANTINE": str(quarantine)},
    )

    assert r.rc == 0, r.stderr
    assert "pg_dropcluster called" not in r.stdout
    assert str(quarantine) in r.stdout


@pytest.mark.unit
def test_ubuntu_preserve_pgdata_verifies_pg_lsclusters_row_removed(tmp_path, bash):
    data = tmp_path / "pgdata"
    etcdir = tmp_path / "etc-postgresql" / "16" / "main"
    quarantine = tmp_path / "quarantine"
    _make_valid_pgdata(data)
    etcdir.mkdir(parents=True)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      SUDO=()
      PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR="${ETCDIR:?}"
      PGPROVISION_UBUNTU_QUARANTINE_ROOT="${QUARANTINE:?}"
      load_os_module
      pg_lsclusters() { printf '16 main 5432 down postgres %s log\\n' "$DATA_DIR"; }
      os_uninstall_cluster
        """,
        env={"DATA": str(data), "ETCDIR": str(etcdir), "QUARANTINE": str(quarantine)},
    )

    assert r.rc == 1
    assert "still reports PostgreSQL 16/main" in r.stderr


@pytest.mark.unit
def test_ubuntu_preserve_pgdata_keeps_valid_pgdata_layout(tmp_path, bash):
    data = tmp_path / "pgdata"
    etcdir = tmp_path / "etc-postgresql" / "16" / "main"
    quarantine = tmp_path / "quarantine"
    _make_valid_pgdata(data)
    etcdir.mkdir(parents=True)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      SUDO=()
      PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR="${ETCDIR:?}"
      PGPROVISION_UBUNTU_QUARANTINE_ROOT="${QUARANTINE:?}"
      load_os_module
      pg_lsclusters() { [[ -d "${PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR}" ]] && printf '16 main 5432 down postgres %s log\\n' "$DATA_DIR"; }
      os_uninstall_cluster
      test -f "$DATA_DIR/PG_VERSION"
      test -f "$DATA_DIR/global/pg_control"
        """,
        env={"DATA": str(data), "ETCDIR": str(etcdir), "QUARANTINE": str(quarantine)},
    )

    assert r.rc == 0, r.stderr
    assert (data / "PG_VERSION").exists()
    assert (data / "global" / "pg_control").exists()


@pytest.mark.unit
def test_ubuntu_preserve_pgdata_restores_config_if_deregistration_fails(tmp_path, bash):
    data = tmp_path / "pgdata"
    etcdir = tmp_path / "etc-postgresql" / "16" / "main"
    quarantine = tmp_path / "quarantine"
    _make_valid_pgdata(data)
    etcdir.mkdir(parents=True)
    (etcdir / "postgresql.conf").write_text("# config\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      SUDO=()
      PGPROVISION_UBUNTU_CLUSTER_CONFIG_DIR="${ETCDIR:?}"
      PGPROVISION_UBUNTU_QUARANTINE_ROOT="${QUARANTINE:?}"
      load_os_module
      pg_lsclusters() { printf '16 main 5432 down postgres %s log\\n' "$DATA_DIR"; }
      os_uninstall_cluster
        """,
        env={"DATA": str(data), "ETCDIR": str(etcdir), "QUARANTINE": str(quarantine)},
    )

    assert r.rc == 1
    assert etcdir.exists()
    assert (etcdir / "postgresql.conf").exists()
    assert "still reports PostgreSQL 16/main" in r.stderr


@pytest.mark.unit
def test_ubuntu_remove_pgdata_calls_pg_dropcluster(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      REMOVE_PGDATA=true
      SUDO=()
      load_os_module
      pg_lsclusters() {
        printf '16 main 5432 down postgres %s log\\n' "$DATA_DIR"
      }
      pg_dropcluster() {
        echo "pg_dropcluster $*"
        rm -rf -- "$DATA_DIR"
      }
      os_uninstall_cluster
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 0, r.stderr
    assert "pg_dropcluster --stop 16 main" in r.stdout
    assert not data.exists()


@pytest.mark.unit
def test_ubuntu_remove_pgdata_refuses_mismatched_registered_cluster(tmp_path, bash):
    confirmed = tmp_path / "confirmed"
    registered = tmp_path / "registered"
    _make_valid_pgdata(confirmed)
    _make_valid_pgdata(registered)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${CONFIRMED:?}"
      REMOVE_PGDATA=true
      SUDO=()
      load_os_module
      pg_lsclusters() {
        printf '16 main 5432 down postgres %s log\\n' "${REGISTERED:?}"
      }
      pg_dropcluster() { echo "pg_dropcluster should not run"; return 0; }
      os_uninstall_cluster
        """,
        env={"CONFIRMED": str(confirmed), "REGISTERED": str(registered)},
    )

    assert r.rc == 1
    assert "does not match confirmed uninstall target" in r.stderr
    assert "pg_dropcluster should not run" not in r.stdout
    assert confirmed.exists()
    assert registered.exists()


@pytest.mark.unit
def test_rhel_removes_systemd_override(tmp_path, bash):
    systemd = tmp_path / "systemd"
    dropin = systemd / "postgresql-16.service.d"
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)
    dropin.mkdir(parents=True)
    override = dropin / "override.conf"
    override.write_text("[Service]\nEnvironment=PGDATA=x\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=rhel
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      SUDO=()
      PGPROVISION_RHEL_SYSTEMD_DIR="${SYSTEMD:?}"
      load_os_module
      _rhel_service_name() { printf 'postgresql-16\\n'; }
      systemctl() { echo "systemctl $*"; return 0; }
      os_uninstall_cluster
        """,
        env={"DATA": str(data), "SYSTEMD": str(systemd)},
    )

    assert r.rc == 0, r.stderr
    assert "rm -f --" in r.stdout
    assert str(override) in r.stdout
    assert "systemctl daemon-reload" in r.stdout
    assert not override.exists()


@pytest.mark.unit
def test_purge_packages_ubuntu_command_patterns(bash):
    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=()
      load_os_module
      dpkg() { printf 'ii  postgresql-16-pgvector  0.8.1  amd64  pgvector\\n'; }
      apt-get() { echo "apt-get $*"; return 0; }
      os_purge_packages
        """
    )

    assert r.rc == 0, r.stderr
    assert (
        "apt-get purge -y postgresql-16 postgresql-client-16 postgresql-16-pgvector"
        in r.stdout
    )
    assert "apt-get autoremove -y" in r.stdout


@pytest.mark.unit
def test_ubuntu_purge_skips_absent_pgvector(bash):
    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=()
      load_os_module
      dpkg() { return 0; }
      apt-get() { echo "apt-get $*"; return 0; }
      os_purge_packages
        """
    )

    assert r.rc == 0, r.stderr
    purge_line = next(line for line in r.stdout.splitlines() if "apt-get purge" in line)
    assert purge_line.endswith("postgresql-16 postgresql-client-16")
    assert "pgvector" not in purge_line
    assert "apt-get autoremove -y" in r.stdout
    assert "skipping package-specific purge" in r.stderr


@pytest.mark.unit
def test_purge_packages_rhel_command_patterns(bash):
    r = bash(
        """
      OS_FAMILY=rhel
      PG_VERSION=16
      SUDO=()
      load_os_module
      dnf() { echo "dnf $*"; return 0; }
      os_purge_packages
        """
    )

    assert r.rc == 0, r.stderr
    assert "dnf -y remove postgresql16* pgvector_16" in r.stdout


@pytest.mark.unit
def test_ubuntu_stop_cluster_skips_missing_unit(bash):
    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=()
      load_os_module
      systemctl() {
        case "$1" in
          cat) return 1 ;;
          stop|disable) echo "unexpected systemctl $*"; return 0 ;;
          *) return 0 ;;
        esac
      }
      os_stop_cluster
        """
    )

    assert r.rc == 0, r.stderr
    assert "unexpected systemctl" not in r.stdout
    assert "Service unit postgresql@16-main not found" in r.stderr


@pytest.mark.unit
def test_ubuntu_cleanup_repo_removes_known_files(tmp_path, bash):
    repo_file = tmp_path / "pgdg.list"
    keyring = tmp_path / "postgresql.gpg"
    repo_file.write_text("deb test\n", encoding="utf-8")
    keyring.write_text("key\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=()
      PGPROVISION_UBUNTU_PGDG_LIST="${REPO_FILE:?}"
      PGPROVISION_UBUNTU_PGDG_KEYRING="${KEYRING:?}"
      load_os_module
      apt-get() { echo "apt-get $*"; return 0; }
      os_cleanup_repo
        """,
        env={"REPO_FILE": str(repo_file), "KEYRING": str(keyring)},
    )

    assert r.rc == 0, r.stderr
    assert not repo_file.exists()
    assert not keyring.exists()
    assert "apt-get update" in r.stdout


@pytest.mark.unit
def test_rhel_cleanup_repo_removes_gpg_keys(tmp_path, bash):
    repo_dir = tmp_path / "yum.repos.d"
    gpg_dir = tmp_path / "rpm-gpg"
    repo_dir.mkdir()
    gpg_dir.mkdir()
    repo_file = repo_dir / "pgdg-redhat-all.repo"
    legacy_repo_file = repo_dir / "pgdg-redhat.repo"
    gpg_key = gpg_dir / "PGDG-RPM-GPG-KEY-RHEL"
    repo_file.write_text("[pgdg]\n", encoding="utf-8")
    legacy_repo_file.write_text("[pgdg-legacy]\n", encoding="utf-8")
    gpg_key.write_text("key\n", encoding="utf-8")

    r = bash(
        """
      OS_FAMILY=rhel
      PG_VERSION=16
      SUDO=()
      PGPROVISION_RHEL_REPO_DIR="${REPO_DIR:?}"
      PGPROVISION_RHEL_GPG_KEY_DIR="${GPG_DIR:?}"
      load_os_module
      dnf() { echo "dnf $*"; return 0; }
      os_cleanup_repo
        """,
        env={"REPO_DIR": str(repo_dir), "GPG_DIR": str(gpg_dir)},
    )

    assert r.rc == 0, r.stderr
    assert "dnf -y remove pgdg-redhat-repo" in r.stdout
    assert not repo_file.exists()
    assert not legacy_repo_file.exists()
    assert not gpg_key.exists()
    assert "PGDG-RPM-GPG-KEY-RHEL" in r.stdout


@pytest.mark.unit
def test_user_uninstall_removes_only_owned_paths(tmp_path, bash):
    base = tmp_path / "base"
    inside = base / "data"
    outside = tmp_path / "outside-data"
    runtime = base / "run"
    log_file = base / "log" / "postgresql.log"
    _make_valid_pgdata(inside)
    _make_valid_pgdata(outside)
    runtime.mkdir(parents=True)
    log_file.parent.mkdir(parents=True)
    log_file.write_text("log\n", encoding="utf-8")

    denied = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PGPROVISION_USER_BASE_DIR="${BASE:?}"
      DATA_DIR="${OUTSIDE:?}"
      REMOVE_PGDATA=true
      SUDO=()
      load_os_module
      os_uninstall_cluster
        """,
        env={"BASE": str(base), "OUTSIDE": str(outside)},
    )
    assert denied.rc == 1
    assert outside.exists()
    assert "outside PGPROVISION_USER_BASE_DIR" in denied.stderr

    removed = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PGPROVISION_USER_BASE_DIR="${BASE:?}"
      PGPROVISION_USER_RUNTIME_DIR="${RUNTIME:?}"
      LOG_FILE="${LOG:?}"
      DATA_DIR="${INSIDE:?}"
      REMOVE_PGDATA=true
      UNINSTALL_CONFIRM_TOKEN="uninstall:16:user:${INSIDE:?}"
      PGPROVISION_CONFIRM_UNINSTALL="$UNINSTALL_CONFIRM_TOKEN"
      SUDO=()
      load_os_module
      os_uninstall_cluster
        """,
        env={
            "BASE": str(base),
            "RUNTIME": str(runtime),
            "LOG": str(log_file),
            "INSIDE": str(inside),
        },
    )

    assert removed.rc == 0, removed.stderr
    assert not inside.exists()
    assert outside.exists()


@pytest.mark.unit
def test_user_preserve_uninstall_skips_runtime_overlapping_pgdata(tmp_path, bash):
    base = tmp_path / "base"
    data = base / "data"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PGPROVISION_USER_BASE_DIR="${BASE:?}"
      UNIX_SOCKET_DIR="${DATA:?}"
      DATA_DIR="${DATA:?}"
      REMOVE_PGDATA=false
      SUDO=()
      load_os_module
      os_uninstall_cluster
        """,
        env={"BASE": str(base), "DATA": str(data)},
    )

    assert r.rc == 0, r.stderr
    assert data.exists()
    assert "Skipping runtime directory cleanup because it overlaps PGDATA" in r.stderr


@pytest.mark.unit
def test_user_stop_cluster_fails_when_pg_ctl_unusable(tmp_path, bash):
    data = tmp_path / "data"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      PG_BIN_DIR="${MISSING:?}"
      SUDO=()
      load_os_module
      os_stop_cluster
        """,
        env={"DATA": str(data), "MISSING": str(tmp_path / "missing-bin")},
    )

    assert r.rc == 1
    assert "pg_ctl is not executable" in r.stderr


@pytest.mark.unit
def test_user_stop_cluster_treats_missing_datadir_as_stopped(tmp_path, bash):
    bin_dir = tmp_path / "bin"
    data = tmp_path / "missing-data"
    bin_dir.mkdir()
    pg_ctl = bin_dir / "pg_ctl"
    pg_ctl.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *status* ]]; then exit 4; fi\n'
        'echo unexpected pg_ctl "$@"\n'
        "exit 99\n",
        encoding="utf-8",
    )
    pg_ctl.chmod(0o755)

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      PG_BIN_DIR="${BIN_DIR:?}"
      SUDO=()
      load_os_module
      os_stop_cluster
        """,
        env={"DATA": str(data), "BIN_DIR": str(bin_dir)},
    )

    assert r.rc == 0, r.stderr
    assert "already stopped" in r.stderr
    assert "unexpected pg_ctl" not in r.stdout


@pytest.mark.unit
def test_uninstall_failure_lists_not_yet_attempted_as_skipped(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      PURGE_PACKAGES=true
      REMOVE_PGDG_REPO=true
      SERVICE=postgresql@16-main
      UNINSTALL_CONFIRM_TOKEN="uninstall:16:ubuntu:${DATA:?}"
      os_stop_cluster() { return 6; }
      os_uninstall_cluster() { echo "uninstall should not run"; return 0; }
      os_purge_packages() { echo "purge should not run"; return 0; }
      os_cleanup_repo() { echo "repo should not run"; return 0; }
      execute_uninstall_manifest
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 6
    assert "Cluster uninstall failed at step 'stop_cluster'" in r.stderr
    assert "Skipped uninstall steps:" in r.stderr
    assert "  - uninstall_cluster" in r.stderr
    assert "  - purge_packages" in r.stderr
    assert "  - cleanup_repo" in r.stderr
    assert "  - stop_cluster" not in r.stderr
    assert "should not run" not in r.stdout


@pytest.mark.unit
def test_uninstall_failure_output_lists_recovery_commands(tmp_path, bash):
    data = tmp_path / "pgdata"
    _make_valid_pgdata(data)

    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=16
      DATA_DIR="${DATA:?}"
      PURGE_PACKAGES=true
      REMOVE_PGDG_REPO=true
      SERVICE=postgresql@16-main
      UNINSTALL_CONFIRM_TOKEN="uninstall:16:ubuntu:${DATA:?}"
      os_stop_cluster() { return 0; }
      os_uninstall_cluster() { return 7; }
      os_purge_packages() { echo "purge should not run"; return 0; }
      os_cleanup_repo() { echo "repo should not run"; return 0; }
      execute_uninstall_manifest
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 7
    assert "Cluster uninstall failed at step 'uninstall_cluster'" in r.stderr
    assert "Completed uninstall steps:" in r.stderr
    assert "stop_cluster" in r.stderr
    assert "Skipped uninstall steps:" in r.stderr
    assert "  - purge_packages" in r.stderr
    assert "  - cleanup_repo" in r.stderr
    assert "  - uninstall_cluster" not in r.stderr
    assert "Manual recovery commands" in r.stderr
    assert "pg_lsclusters --no-header" in r.stderr
    assert "--remove-pgdata" in r.stderr
    assert "purge should not run" not in r.stdout


@pytest.mark.unit
def test_load_os_module_requires_uninstall_contract(tmp_path, bash):
    module_dir = tmp_path / "module-root"
    os_dir = module_dir / "os"
    os_dir.mkdir(parents=True)
    (os_dir / "user.sh").write_text(
        textwrap.dedent(
            """
            os_prepare_repos() { :; }
            os_install_packages() { :; }
            os_install_extension_packages() { :; }
            os_init_cluster() { :; }
            os_get_paths() { :; }
            os_restart() { :; }
            os_self_heal() { :; }
            os_stop_cluster() { :; }
            os_uninstall_cluster() { :; }
            os_purge_packages() { :; }
            """
        ),
        encoding="utf-8",
    )

    r = bash(
        """
      SCRIPT_DIR="${MODULE_DIR:?}"
      OS_FAMILY=user
      load_os_module
        """,
        env={"MODULE_DIR": str(module_dir)},
    )

    assert r.rc == 2
    assert "missing:" in r.stderr
    assert "os_cleanup_repo" in r.stderr
