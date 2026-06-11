import hashlib
import tarfile
import textwrap

import pytest


def _write_executable(path, body):
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _fake_pg_bin(
    tmp_path, major="16", initdb_body=None, pg_ctl_body=None, psql_body=None
):
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name in ["postgres", "psql", "initdb", "pg_ctl"]:
        body = f"""\
        #!/usr/bin/env bash
        if [[ "${{1:-}}" == "--version" ]]; then
          echo "{name} (PostgreSQL) {major}.1"
          exit 0
        fi
        exit 0
        """
        _write_executable(bindir / name, body)
    if initdb_body is not None:
        _write_executable(bindir / "initdb", initdb_body)
    if pg_ctl_body is not None:
        _write_executable(bindir / "pg_ctl", pg_ctl_body)
    if psql_body is not None:
        _write_executable(bindir / "psql", psql_body)
    return bindir


def _fake_pg_tarball(tmp_path, major="16"):
    root = tmp_path / "postgresql-16"
    bindir = root / "bin"
    bindir.mkdir(parents=True)
    for name in ["postgres", "psql", "initdb", "pg_ctl"]:
        body = f"""\
        #!/usr/bin/env bash
        if [[ "${{1:-}}" == "--version" ]]; then
          echo "{name} (PostgreSQL) {major}.1"
          exit 0
        fi
        exit 0
        """
        _write_executable(bindir / name, body)
    tarball = tmp_path / "postgresql.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(root, arcname=root.name)
    return tarball, hashlib.sha256(tarball.read_bytes()).hexdigest()


def _make_valid_pgdata(path, major="16"):
    (path / "global").mkdir(parents=True)
    (path / "base").mkdir()
    (path / "pg_wal").mkdir()
    (path / "global" / "pg_control").write_bytes(b"x")
    (path / "PG_VERSION").write_text(f"{major}\n", encoding="utf-8")
    path.chmod(0o700)


def _make_extension_control(bindir, control):
    extension_dir = bindir.parent / "share" / "extension"
    extension_dir.mkdir(parents=True, exist_ok=True)
    (extension_dir / f"{control}.control").write_text(
        "comment = 'test'\n", encoding="utf-8"
    )


@pytest.mark.unit
def test_user_backend_requires_pg_binaries(tmp_path, bash):
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    _write_executable(
        bindir / "psql",
        """\
        #!/usr/bin/env bash
        echo "psql (PostgreSQL) 16.1"
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      load_os_module
      os_install_packages
        """,
        env={"BINDIR": str(bindir)},
    )

    assert r.rc == 2
    assert "Required PostgreSQL 16 binaries" in r.stderr
    assert "postgres" in r.stderr
    assert "initdb" in r.stderr
    assert "pg_ctl" in r.stderr


@pytest.mark.unit
def test_user_backend_uses_bootstrapped_pg_bin_dir(tmp_path, bash):
    tarball, sha256 = _fake_pg_tarball(tmp_path)
    bootdir = tmp_path / "bootstrap-cache"

    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      RUNTIME_REQUESTED_MODE=user
      PG_VERSION=16
      PGPROVISION_BOOTSTRAP_TARBALL="${TARBALL:?}"
      PGPROVISION_BOOTSTRAP_SHA256="${SHA256:?}"
      PGPROVISION_BOOTSTRAP_DIR="${BOOTDIR:?}"
      bootstrap_apply_if_requested
      OS_FAMILY=user
      load_os_module
      os_install_packages
      printf 'PG_BIN_DIR=%s\n' "$PG_BIN_DIR"
        """,
        env={"TARBALL": str(tarball), "SHA256": sha256, "BOOTDIR": str(bootdir)},
    )

    expected = bootdir / "16" / sha256 / "root" / "postgresql-16" / "bin"
    assert r.rc == 0, r.stderr
    assert f"PG_BIN_DIR={expected}" in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_user_backend_defines_full_phase5_contract(tmp_path, bash):
    bindir = _fake_pg_bin(tmp_path)

    r = bash(
        """
      OS_FAMILY=user
      PG_BIN_DIR="${BINDIR:?}"
      load_os_module
      for fn in os_prepare_repos os_install_packages os_install_extension_packages \
                os_init_cluster os_get_paths os_restart os_self_heal os_stop_cluster; do
        declare -F "$fn" >/dev/null || exit 9
        echo "$fn"
      done
        """,
        env={"BINDIR": str(bindir)},
    )

    assert r.rc == 0, r.stderr
    assert "os_stop_cluster" in r.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    ("flag", "control"),
    [
        ("INIT_PG_STAT_STATEMENTS=true", "pg_stat_statements.control"),
        ("INIT_PGVECTOR=true", "vector.control"),
    ],
)
def test_user_extension_package_hook_requires_requested_control_files(
    tmp_path, bash, flag, control
):
    bindir = _fake_pg_bin(tmp_path)

    r = bash(
        f"""
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${{BINDIR:?}}"
      {flag}
      load_os_module
      os_install_extension_packages
        """,
        env={"BINDIR": str(bindir)},
    )

    assert r.rc == 2
    assert "User-mode" in r.stderr
    assert "control file is missing" in r.stderr
    assert control in r.stderr
    assert "MVP" not in r.stderr


@pytest.mark.unit
def test_user_tls_requires_cert_and_key(tmp_path, bash):
    data = tmp_path / "data"
    _make_valid_pgdata(data)

    r = bash(
        """
      RUNTIME_MODE=user
      ENABLE_TLS=true
      DATA_DIR="${DATA:?}"
      validate_tls_prereqs
        """,
        env={"DATA": str(data)},
    )

    assert r.rc == 1
    assert "server.crt or" in r.stderr
    assert "server.key missing" in r.stderr


@pytest.mark.unit
def test_user_tls_cert_key_only_pgdata_can_be_initialized(tmp_path, bash):
    data = tmp_path / "data"
    data.mkdir()
    crt = data / "server.crt"
    key = data / "server.key"
    crt.write_text("crt\n", encoding="utf-8")
    key.write_text("key\n", encoding="utf-8")
    key.chmod(0o600)
    cap = tmp_path / "initdb.log"
    bindir = _fake_pg_bin(
        tmp_path,
        initdb_body="""\
        #!/usr/bin/env bash
        if [[ "${1:-}" == "--version" ]]; then
          echo "initdb (PostgreSQL) 16.1"
          exit 0
        fi
        data=""
        while (($#)); do
          case "$1" in
            -D) data="$2"; shift 2 ;;
            *) shift ;;
          esac
        done
        if find "${data}" -mindepth 1 -maxdepth 1 | grep -q .; then
          echo "data dir was not empty before initdb" >&2
          exit 8
        fi
        echo "initdb -D ${data}" >> "${CAP:?}"
        mkdir -p "${data}/global" "${data}/base" "${data}/pg_wal"
        printf '16\\n' > "${data}/PG_VERSION"
        printf x > "${data}/global/pg_control"
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      DATA_DIR="${DATA:?}"
      ENABLE_TLS=true
      load_os_module
      os_self_heal
      os_init_cluster "$DATA_DIR"
      test -f "$DATA_DIR/server.crt"
      test -f "$DATA_DIR/server.key"
        """,
        env={"BINDIR": str(bindir), "DATA": str(data), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert f"initdb -D {data}" in cap.read_text(encoding="utf-8")
    assert crt.read_text(encoding="utf-8") == "crt\n"
    assert key.read_text(encoding="utf-8") == "key\n"


@pytest.mark.unit
def test_user_tls_cert_key_only_rejects_unsafe_key_before_init(tmp_path, bash):
    data = tmp_path / "data"
    data.mkdir()
    (data / "server.crt").write_text("crt\n", encoding="utf-8")
    key = data / "server.key"
    key.write_text("key\n", encoding="utf-8")
    key.chmod(0o644)
    cap = tmp_path / "initdb.log"
    bindir = _fake_pg_bin(
        tmp_path,
        initdb_body="""\
        #!/usr/bin/env bash
        echo "unexpected initdb" >> "${CAP:?}"
        exit 9
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      DATA_DIR="${DATA:?}"
      ENABLE_TLS=true
      RUNTIME_MODE=user
      load_os_module
      os_init_cluster "$DATA_DIR"
        """,
        env={"BINDIR": str(bindir), "DATA": str(data), "CAP": str(cap)},
    )

    assert r.rc == 1
    assert "server.key must not be group/other-accessible" in r.stderr
    assert not cap.exists()


@pytest.mark.unit
def test_user_pgss_uses_user_psql(tmp_path, bash):
    cap = tmp_path / "psql.log"
    bindir = _fake_pg_bin(
        tmp_path,
        psql_body="""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "${CAP:?}"
        exit 0
        """,
    )
    _make_extension_control(bindir, "pg_stat_statements")

    r = bash(
        """
      sudo() { echo "sudo $*" >> "${CAP:?}"; return 99; }
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          *) command id "$@" ;;
        esac
      }
      runtime_init user false
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      PGPROVISION_USER_RUNTIME_DIR="${RUNTIME:?}"
      PORT=55433
      INIT_PG_STAT_STATEMENTS=true
      load_os_module
      os_install_extension_packages
      conditionally_init_pg_stat_statements
      cat "${CAP:?}"
        """,
        env={"BINDIR": str(bindir), "RUNTIME": str(tmp_path / "run"), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "sudo" not in r.stdout
    assert f"-h {tmp_path / 'run'}" in r.stdout
    assert "-p 55433" in r.stdout
    assert "-U appuser" in r.stdout
    assert "CREATE EXTENSION IF NOT EXISTS pg_stat_statements" in r.stdout


@pytest.mark.unit
def test_user_backend_initdb_for_empty_pgdata(tmp_path, bash):
    data = tmp_path / "data"
    cap = tmp_path / "initdb.log"
    bindir = _fake_pg_bin(
        tmp_path,
        initdb_body="""\
        #!/usr/bin/env bash
        if [[ "${1:-}" == "--version" ]]; then
          echo "initdb (PostgreSQL) 16.1"
          exit 0
        fi
        data=""
        while (($#)); do
          case "$1" in
            -D) data="$2"; shift 2 ;;
            *) shift ;;
          esac
        done
        echo "initdb -D ${data}" >> "${CAP:?}"
        mkdir -p "${data}/global" "${data}/base" "${data}/pg_wal"
        printf '16\\n' > "${data}/PG_VERSION"
        printf x > "${data}/global/pg_control"
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      DATA_DIR="${DATA:?}"
      load_os_module
      os_init_cluster "$DATA_DIR"
        """,
        env={"BINDIR": str(bindir), "DATA": str(data), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert f"initdb -D {data}" in cap.read_text(encoding="utf-8")
    assert (data / "global" / "pg_control").exists()


@pytest.mark.unit
def test_user_backend_reuses_valid_pgdata(tmp_path, bash):
    data = tmp_path / "data"
    cap = tmp_path / "initdb.log"
    _make_valid_pgdata(data)
    bindir = _fake_pg_bin(
        tmp_path,
        initdb_body="""\
        #!/usr/bin/env bash
        if [[ "${1:-}" == "--version" ]]; then
          echo "initdb (PostgreSQL) 16.1"
          exit 0
        fi
        echo "unexpected initdb" >> "${CAP:?}"
        exit 9
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      DATA_DIR="${DATA:?}"
      load_os_module
      os_init_cluster "$DATA_DIR"
        """,
        env={"BINDIR": str(bindir), "DATA": str(data), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert not cap.exists()


@pytest.mark.unit
def test_user_backend_rejects_repo_pgdg(bash):
    r = bash(
        """
      OS_FAMILY=user
      load_os_module
      os_prepare_repos pgdg
        """
    )

    assert r.rc == 2
    assert "cannot prepare --repo pgdg" in r.stderr


@pytest.mark.unit
def test_user_mode_empty_socket_group_is_noop(bash):
    r = bash(
        """
      runtime_init user false
      sudo() { echo "sudo called"; return 99; }
      groupadd() { echo "groupadd called"; return 99; }
      ensure_socket_group_and_members ""
        """
    )

    assert r.rc == 0, r.stderr
    assert "sudo called" not in r.stdout
    assert "groupadd called" not in r.stdout


@pytest.mark.unit
def test_user_socket_group_requires_existing_membership(bash):
    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      groupadd() { echo "groupadd called"; return 99; }
      usermod() { echo "usermod called"; return 99; }
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          -nG) echo othergroup ;;
          *) command id "$@" ;;
        esac
      }
      getent() {
        if [[ "${1:-}" == "group" && "${2:-}" == "pgclients" ]]; then
          echo "pgclients:x:123:"
          return 0
        fi
        command getent "$@"
      }
      runtime_init user false
      ensure_socket_group_and_members pgclients
        """
    )

    assert r.rc == 2
    assert "not a member" in r.stderr
    assert "sudo called" not in r.stdout
    assert "groupadd called" not in r.stdout
    assert "usermod called" not in r.stdout


@pytest.mark.unit
def test_user_socket_only_sets_local_policy(tmp_path, bash):
    data = tmp_path / "data"
    data.mkdir()
    (data / "postgresql.conf").touch()
    (data / "pg_hba.conf").touch()
    runtime = tmp_path / "run"

    r = bash(
        """
      parse_args --user-mode --socket-only --listen-addresses localhost \
        --data-dir "${DATA:?}" --user-base-dir "${BASE:?}" --user-runtime-dir "${RUNTIME:?}"
      resolve_mode_defaults
      RUNTIME_MODE="$RUNTIME_REQUESTED_MODE"
      OS_FAMILY=user
      load_os_module
      eval "$(os_get_paths)"
      apply_dropin_config "$CONF_FILE" "$DATA_DIR"
      apply_hba_policy "$HBA_FILE"
      cat "${DATA:?}/conf.d/99-pgprovision.conf"
      echo "--hba--"
      cat "$HBA_FILE"
      echo "--socket--"
      printf '%s\\n' "$UNIX_SOCKET_DIR"
        """,
        env={
            "DATA": str(data),
            "BASE": str(tmp_path / "base"),
            "RUNTIME": str(runtime),
        },
    )

    assert r.rc == 0, r.stderr
    assert "listen_addresses = ''" in r.stdout
    assert f"unix_socket_directories = '{runtime}'" in r.stdout
    assert "host    all             all             127.0.0.1/32" in r.stdout
    assert "reject" in r.stdout
    assert f"\n{runtime}\n" in r.stdout


@pytest.mark.unit
def test_user_admin_paths_use_runtime_psql_without_sudo(tmp_path, bash):
    cap = tmp_path / "psql.log"
    bindir = _fake_pg_bin(
        tmp_path,
        psql_body="""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "${CAP:?}"
        exit 0
        """,
    )

    r = bash(
        """
      sudo() { echo "sudo $*" >> "${CAP:?}"; return 99; }
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          *) command id "$@" ;;
        esac
      }
      runtime_init user false
      PG_BIN_DIR="${BINDIR:?}"
      PGPROVISION_USER_RUNTIME_DIR="${RUNTIME:?}"
      PORT=55433
      ADMIN_GROUP_ROLE=dba_group
      ADMIN_DBROLE=dba
      DISABLE_POSTGRES_LOGIN=true
      LOCAL_MAP_ENTRIES=("appuser:appuser")
      setup_role_mappings_and_admin
      cat "${CAP:?}"
        """,
        env={"BINDIR": str(bindir), "RUNTIME": str(tmp_path / "run"), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "sudo" not in r.stdout
    assert f"-h {tmp_path / 'run'}" in r.stdout
    assert "-p 55433" in r.stdout
    assert "-U appuser" in r.stdout
    assert "CREATE ROLE" in r.stdout
    assert "IF EXISTS (SELECT FROM pg_roles WHERE rolname='postgres')" in r.stdout
    assert "ALTER ROLE postgres NOLOGIN" in r.stdout


@pytest.mark.unit
def test_user_admin_paths_fail_fast_on_psql_error(tmp_path, bash):
    cap = tmp_path / "psql.log"
    bindir = _fake_pg_bin(
        tmp_path,
        psql_body="""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "${CAP:?}"
        exit 7
        """,
    )

    r = bash(
        """
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          *) command id "$@" ;;
        esac
      }
      runtime_init user false
      PG_BIN_DIR="${BINDIR:?}"
      PGPROVISION_USER_RUNTIME_DIR="${RUNTIME:?}"
      ADMIN_GROUP_ROLE=dba_group
      setup_role_mappings_and_admin
        """,
        env={"BINDIR": str(bindir), "RUNTIME": str(tmp_path / "run"), "CAP": str(cap)},
    )

    assert r.rc == 1
    assert "create group dba_group failed" in r.stderr


@pytest.mark.unit
def test_user_admin_failure_skips_disable_postgres_login(tmp_path, bash):
    cap = tmp_path / "psql.log"

    r = bash(
        """
      CAP="${CAP:?}"
      runtime_psql() {
        printf '%s\n' "$*" >> "$CAP"
        case "$*" in
          *"dba_group"*) return 7 ;;
          *"ALTER ROLE postgres NOLOGIN"*) echo "unexpected alter" >> "$CAP"; return 0 ;;
        esac
        return 0
      }
      ADMIN_GROUP_ROLE=dba_group
      DISABLE_POSTGRES_LOGIN=true
      setup_role_mappings_and_admin
        """,
        env={"CAP": str(cap)},
    )

    assert r.rc == 1
    assert "create group dba_group failed" in r.stderr
    assert "ALTER ROLE postgres NOLOGIN" not in cap.read_text(encoding="utf-8")


@pytest.mark.unit
def test_user_get_paths_are_user_owned(tmp_path, bash):
    base = tmp_path / "base"
    runtime = tmp_path / "run"
    data = base / "data"

    r = bash(
        """
      OS_FAMILY=user
      PGPROVISION_USER_BASE_DIR="${BASE:?}"
      PGPROVISION_USER_RUNTIME_DIR="${RUNTIME:?}"
      DATA_DIR="${DATA:?}"
      load_os_module
      eval "$(os_get_paths)"
      printf 'CONF=%s\nHBA=%s\nIDENT=%s\nDATA=%s\nSERVICE=%s\nSOCKET=%s\nLOG=%s\n' \
        "$CONF_FILE" "$HBA_FILE" "$IDENT_FILE" "$DATA_DIR" "$SERVICE" "$UNIX_SOCKET_DIR" "$LOG_FILE"
        """,
        env={"BASE": str(base), "RUNTIME": str(runtime), "DATA": str(data)},
    )

    assert r.rc == 0, r.stderr
    assert f"CONF={data}/postgresql.conf" in r.stdout
    assert f"HBA={data}/pg_hba.conf" in r.stdout
    assert f"IDENT={data}/pg_ident.conf" in r.stdout
    assert f"DATA={data}" in r.stdout
    assert f"SERVICE=user:{data}" in r.stdout
    assert f"SOCKET={runtime}" in r.stdout
    assert f"LOG={base}/log/postgresql.log" in r.stdout


@pytest.mark.unit
def test_user_restart_uses_pg_ctl(tmp_path, bash):
    data = tmp_path / "data"
    data.mkdir()
    cap = tmp_path / "pg_ctl.log"
    bindir = _fake_pg_bin(
        tmp_path,
        pg_ctl_body="""\
        #!/usr/bin/env bash
        if [[ "${1:-}" == "--version" ]]; then
          echo "pg_ctl (PostgreSQL) 16.1"
          exit 0
        fi
        echo "pg_ctl $*" >> "${CAP:?}"
        case "$*" in
          *" status"*) exit 1 ;;
          *) exit 0 ;;
        esac
        """,
    )

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      DATA_DIR="${DATA:?}"
      LOG_FILE="${LOG:?}"
      load_os_module
      os_restart "user:${DATA}"
        """,
        env={
            "BINDIR": str(bindir),
            "DATA": str(data),
            "LOG": str(tmp_path / "postgresql.log"),
            "CAP": str(cap),
        },
    )

    assert r.rc == 0, r.stderr
    log = cap.read_text(encoding="utf-8")
    assert f"pg_ctl -D {data} status" in log
    assert f"pg_ctl -D {data} -l {tmp_path / 'postgresql.log'} start" in log
