import pytest


def _write_executable(path, body):
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.unit
def test_destroy_requires_matching_confirmation(bash):
    ok = bash(
        """
      DESTROY_DB=appdb
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      validate_destroy_request
        """
    )
    assert ok.rc == 0, ok.stderr

    bad = bash(
        """
      DESTROY_DB=appdb
      PGPROVISION_CONFIRM_DESTROY_DB=wrongdb
      validate_destroy_request
        """
    )
    assert bad.rc == 2
    assert "Destroy confirmation mismatch" in bad.stderr
    assert "Expected confirmation: appdb" in bad.stderr
    assert "Provided confirmation: wrongdb" in bad.stderr


@pytest.mark.unit
def test_destroy_confirmation_validated_after_env_file(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("DESTROY_DB=envdb\n", encoding="utf-8")

    r = bash(
        """
      parse_args --destroy-db clidb --confirm-destroy-db clidb --env-file "$ENVF"
      load_env_file
      validate_destroy_request
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 2
    assert "Expected confirmation: envdb" in r.stderr
    assert "Provided confirmation: clidb" in r.stderr


@pytest.mark.unit
def test_destroy_confirmation_env_file_can_confirm_final_destroy_db(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text(
        "DESTROY_DB=envdb\nPGPROVISION_CONFIRM_DESTROY_DB=envdb\n",
        encoding="utf-8",
    )

    r = bash(
        """
      parse_args --destroy-db clidb --confirm-destroy-db clidb --env-file "$ENVF"
      load_env_file
      validate_destroy_request
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr


@pytest.mark.unit
def test_destroy_confirmation_env_is_pgprovision_confirm_destroy_db(bash):
    r = bash(
        """
      parse_args --destroy-db appdb
      validate_destroy_request
        """,
        env={"PGPROVISION_CONFIRM_DESTROY_DB": "appdb"},
    )
    assert r.rc == 0, r.stderr


@pytest.mark.unit
def test_destroy_requires_reachable_cluster(bash):
    r = bash(
        """
      DESTROY_DB=appdb
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      provision_psql() { echo "connection refused" >&2; return 7; }
      validate_destroy_request
      destroy_db_and_user
        """
    )

    assert r.rc == 1
    assert "not reachable" in r.stderr
    assert "database=postgres" in r.stderr
    assert "pg_ctlcluster" in r.stderr
    assert "connection refused" in r.stderr


@pytest.mark.unit
def test_destroy_psql_uses_configured_port(tmp_path, bash):
    cap = tmp_path / "psql_args.txt"

    r = bash(
        """
      CAP="${CAP:?}"
      PORT=5544
      psql() {
        printf '%s\n' "$*" > "$CAP"
        return 0
      }
      provision_psql postgres -c "SELECT 1;"
      cat "$CAP"
        """,
        env={"CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "-p 5544" in r.stdout
    assert "-d postgres" in r.stdout


@pytest.mark.unit
def test_destroy_psql_uses_configured_socket_dir(tmp_path, bash):
    cap = tmp_path / "psql_args.txt"

    r = bash(
        """
      CAP="${CAP:?}"
      UNIX_SOCKET_DIR=/tmp/pgprov-socket
      psql() {
        printf '%s\n' "$*" > "$CAP"
        return 0
      }
      provision_psql postgres -c "SELECT 1;"
      cat "$CAP"
        """,
        env={"CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "-h /tmp/pgprov-socket" in r.stdout


@pytest.mark.unit
def test_destroy_rejects_blocklisted_database(bash):
    for name in ["postgres", "template0", "template1", "pg_internal"]:
        r = bash(
            """
      DRY_RUN=true
      DESTROY_DB="$DBNAME"
      validate_destroy_request
            """,
            env={"DBNAME": name},
        )
        assert r.rc == 2
        assert "protected database" in r.stderr


@pytest.mark.unit
def test_destroy_rejects_overlong_database_or_role_names(bash):
    overlong = "a" * 64

    db = bash(
        """
      DRY_RUN=true
      DESTROY_DB="$NAME"
      validate_destroy_request
        """,
        env={"NAME": overlong},
    )

    assert db.rc == 2
    assert "at most 63 bytes" in db.stderr

    role = bash(
        """
      DRY_RUN=true
      DESTROY_DB=appdb
      DESTROY_USER="$NAME"
      validate_destroy_request
        """,
        env={"NAME": overlong},
    )

    assert role.rc == 2
    assert "at most 63 bytes" in role.stderr


@pytest.mark.unit
def test_destroy_user_rejects_admin_dbrole_and_current_user(bash):
    admin = bash(
        """
      DRY_RUN=true
      DESTROY_DB=appdb
      DESTROY_USER=dba
      ADMIN_DBROLE=dba
      validate_destroy_request
        """
    )
    assert admin.rc == 2
    assert "admin DB role" in admin.stderr

    current = bash(
        """
      DESTROY_DB=appdb
      DESTROY_USER=runner
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      provision_psql() {
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*) printf '%s\n' runner; return 0 ;;
        esac
        return 0
      }
      validate_destroy_request
      destroy_db_and_user
        """
    )
    assert current.rc == 2
    assert "current SQL user" in current.stderr


@pytest.mark.unit
def test_destroy_only_exits_after_destroy(tmp_path, bash):
    cap = tmp_path / "calls.txt"
    sqlcap = tmp_path / "sql.txt"

    r = bash(
        """
      CAP="${CAP:?}"
      SQLCAP="${SQLCAP:?}"
      : > "$CAP"
      : > "$SQLCAP"
      require_root_or_sudo() { :; }
      id() { if [[ "${1:-}" == "-u" ]]; then echo 0; else command id "$@"; fi; }
      os_detect() { echo "os_detect called" >> "$CAP"; return 44; }
      provision_psql() {
        local db="$1"
        shift
        echo "psql ${db} $*" >> "$CAP"
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*) printf '%s\n' postgres; return 0 ;;
        esac
        cat >> "$SQLCAP"
      }
      shred() {
        local last=""
        for last in "$@"; do :; done
        rm -f "$last"
      }
      ( main --destroy-db appdb --confirm-destroy-db appdb --destroy-only )
      rc=$?
      cat "$CAP"
      echo "--sql--"
      cat "$SQLCAP"
      exit "$rc"
        """,
        env={"CAP": str(cap), "SQLCAP": str(sqlcap)},
    )

    assert r.rc == 0, r.stderr
    assert "os_detect called" not in r.stdout
    assert 'DROP DATABASE IF EXISTS "appdb";' in r.stdout


@pytest.mark.unit
def test_destroy_dry_run_prints_manifest_without_psql(bash):
    r = bash(
        """
      provision_psql() { echo "psql called"; return 99; }
      main --destroy-db appdb --destroy-only --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Logical destroy manifest" in r.stdout
    assert "destroy_db: appdb" in r.stdout
    assert "continue_provision: false" in r.stdout
    assert "psql called" not in r.stdout
    assert "Provision dry-run manifest" not in r.stdout


@pytest.mark.unit
def test_destroy_dry_run_can_print_follow_on_provision_manifest(bash):
    r = bash(
        """
      provision_psql() { echo "psql called"; return 99; }
      main --destroy-db appdb --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Logical destroy manifest" in r.stdout
    assert "continue_provision: true" in r.stdout
    assert "Provision dry-run manifest" in r.stdout
    assert "psql called" not in r.stdout


@pytest.mark.unit
def test_destroy_sql_terminates_backends_and_drops_db(tmp_path, bash):
    sqlcap = tmp_path / "sql.txt"

    r = bash(
        """
      SQLCAP="${SQLCAP:?}"
      : > "$SQLCAP"
      DESTROY_DB=appdb
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      provision_psql() {
        local db="$1"
        shift
        [[ "$db" == postgres ]] || return 8
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*) printf '%s\n' postgres; return 0 ;;
        esac
        cat >> "$SQLCAP"
      }
      shred() {
        local last=""
        for last in "$@"; do :; done
        rm -f "$last"
      }
      validate_destroy_request
      destroy_db_and_user
      cat "$SQLCAP"
        """,
        env={"SQLCAP": str(sqlcap)},
    )

    assert r.rc == 0, r.stderr
    assert "SELECT pg_terminate_backend(pid)" in r.stdout
    assert "FROM pg_stat_activity" in r.stdout
    assert "WHERE datname = 'appdb'" in r.stdout
    assert "AND pid <> pg_backend_pid();" in r.stdout
    assert 'DROP DATABASE IF EXISTS "appdb";' in r.stdout
    assert "DROP ROLE" not in r.stdout


@pytest.mark.unit
def test_destroy_user_optional_drop_role(tmp_path, bash):
    sqlcap = tmp_path / "sql.txt"

    r = bash(
        """
      SQLCAP="${SQLCAP:?}"
      : > "$SQLCAP"
      DESTROY_DB=appdb
      DESTROY_USER='app"role'
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      provision_psql() {
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*) printf '%s\n' postgres; return 0 ;;
        esac
        cat >> "$SQLCAP"
      }
      shred() {
        local last=""
        for last in "$@"; do :; done
        rm -f "$last"
      }
      validate_destroy_request
      destroy_db_and_user
      cat "$SQLCAP"
        """,
        env={"SQLCAP": str(sqlcap)},
    )

    assert r.rc == 0, r.stderr
    assert 'DROP ROLE IF EXISTS "app""role";' in r.stdout


@pytest.mark.unit
def test_destroy_user_mode_uses_runtime_psql(tmp_path, bash):
    cap = tmp_path / "psql_args.txt"
    sqlcap = tmp_path / "sql.txt"
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    _write_executable(
        bindir / "psql",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "${CAP:?}"
case "$*" in
  *"SELECT 1;"*) exit 0 ;;
  *"SELECT current_user;"*) printf '%s\n' appuser; exit 0 ;;
esac
cat >> "${SQLCAP:?}"
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
      ( main --user-mode --pg-bin-dir "${BINDIR:?}" --user-runtime-dir "${RUNTIME:?}" \
        --port 55433 --destroy-db appdb --confirm-destroy-db appdb --destroy-only )
      echo "--args--"
      cat "${CAP:?}"
      echo "--sql--"
      cat "${SQLCAP:?}"
        """,
        env={
            "BINDIR": str(bindir),
            "RUNTIME": str(tmp_path / "run"),
            "CAP": str(cap),
            "SQLCAP": str(sqlcap),
        },
    )

    assert r.rc == 0, r.stderr
    assert "sudo" not in r.stdout
    assert f"-h {tmp_path / 'run'}" in r.stdout
    assert "-p 55433" in r.stdout
    assert "-U appuser" in r.stdout
    assert 'DROP DATABASE IF EXISTS "appdb";' in r.stdout


@pytest.mark.unit
def test_destroy_user_mode_refuses_current_user_before_drop(tmp_path, bash):
    cap = tmp_path / "psql_args.txt"
    sqlcap = tmp_path / "sql.txt"
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    _write_executable(
        bindir / "psql",
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "${CAP:?}"
case "$*" in
  *"SELECT 1;"*) exit 0 ;;
  *"SELECT current_user;"*) printf '%s\n' appuser; exit 0 ;;
esac
cat >> "${SQLCAP:?}"
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
      main --user-mode --pg-bin-dir "${BINDIR:?}" --user-runtime-dir "${RUNTIME:?}" \
        --port 55433 --destroy-db appdb --destroy-user appuser \
        --confirm-destroy-db appdb --destroy-only
        """,
        env={
            "BINDIR": str(bindir),
            "RUNTIME": str(tmp_path / "run"),
            "CAP": str(cap),
            "SQLCAP": str(sqlcap),
        },
    )

    assert r.rc == 2
    assert "current SQL user" in r.stderr
    assert not sqlcap.exists()


@pytest.mark.unit
def test_destroy_current_user_ignores_psql_stderr_warnings(tmp_path, bash):
    sqlcap = tmp_path / "sql.txt"

    r = bash(
        """
      SQLCAP="${SQLCAP:?}"
      DESTROY_DB=appdb
      DESTROY_USER=appuser
      PGPROVISION_CONFIRM_DESTROY_DB=appdb
      provision_psql() {
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*)
            echo "WARNING: noisy extension" >&2
            printf '%s\n' appuser
            return 0
            ;;
        esac
        cat >> "$SQLCAP"
      }
      validate_destroy_request
      destroy_db_and_user
        """,
        env={"SQLCAP": str(sqlcap)},
    )

    assert r.rc == 2
    assert "current SQL user" in r.stderr
    assert not sqlcap.exists()


@pytest.mark.unit
def test_user_mode_destroy_continue_runs_checks_before_drop(tmp_path, bash):
    cap = tmp_path / "psql.log"
    sqlcap = tmp_path / "sql.txt"
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name in ["postgres", "initdb", "pg_ctl", "psql"]:
        _write_executable(
            bindir / name,
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "--version" ]]; then
  echo "{name} (PostgreSQL) 16.1"
  exit 0
fi
printf '%s\\n' "$*" >> "${{CAP:?}}"
cat >> "${{SQLCAP:?}}"
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
      main --user-mode --pg-bin-dir "${BINDIR:?}" --user-runtime-dir "${RUNTIME:?}" \
        --pg-version 16 \
        --destroy-db appdb --confirm-destroy-db appdb --init-pgvector
        """,
        env={
            "BINDIR": str(bindir),
            "RUNTIME": str(tmp_path / "run"),
            "CAP": str(cap),
            "SQLCAP": str(sqlcap),
        },
    )

    assert r.rc == 2
    assert "vector.control" in r.stderr
    assert not cap.exists()
    assert not sqlcap.exists()


@pytest.mark.unit
def test_user_mode_destroy_continue_checks_layout_before_drop(tmp_path, bash):
    cap = tmp_path / "psql.log"
    sqlcap = tmp_path / "sql.txt"
    blocked_parent = tmp_path / "not-a-dir"
    blocked_parent.write_text("file blocks directory creation\n", encoding="utf-8")
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name in ["postgres", "initdb", "pg_ctl", "psql"]:
        _write_executable(
            bindir / name,
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "--version" ]]; then
  echo "{name} (PostgreSQL) 16.1"
  exit 0
fi
printf '%s\\n' "$*" >> "${{CAP:?}}"
cat >> "${{SQLCAP:?}}"
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
      main --user-mode --pg-bin-dir "${BINDIR:?}" \
        --pg-version 16 \
        --user-base-dir "${BLOCKED:?}/base" --data-dir "${BLOCKED:?}/base/data" \
        --destroy-db appdb --confirm-destroy-db appdb
        """,
        env={
            "BINDIR": str(bindir),
            "BLOCKED": str(blocked_parent),
            "CAP": str(cap),
            "SQLCAP": str(sqlcap),
        },
    )

    assert r.rc != 0
    assert "create user data dir" in r.stderr or "Not a directory" in r.stderr
    assert not cap.exists()
    assert not sqlcap.exists()


@pytest.mark.unit
def test_user_mode_destroy_invalid_confirm_does_not_create_layout(tmp_path, bash):
    base = tmp_path / "base"

    r = bash(
        """
      main --user-mode --user-base-dir "${BASE:?}" \
        --destroy-db appdb --confirm-destroy-db wrongdb
        """,
        env={"BASE": str(base)},
    )

    assert r.rc == 2
    assert "Destroy confirmation mismatch" in r.stderr
    assert not base.exists()


@pytest.mark.unit
def test_user_mode_destroy_continue_checks_default_socket_group_before_drop(
    tmp_path, bash
):
    cap = tmp_path / "psql.log"
    sqlcap = tmp_path / "sql.txt"
    base = tmp_path / "base"
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name in ["postgres", "initdb", "pg_ctl", "psql"]:
        _write_executable(
            bindir / name,
            f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "--version" ]]; then
  echo "{name} (PostgreSQL) 16.1"
  exit 0
fi
printf '%s\\n' "$*" >> "${{CAP:?}}"
cat >> "${{SQLCAP:?}}"
""",
        )

    r = bash(
        """
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          -nG) echo "appuser pgclients" ;;
          *) command id "$@" ;;
        esac
      }
      getent() {
        if [[ "${1:-}" == "group" && "${2:-}" == "pgclients" ]]; then
          echo "pgclients:x:123:appuser"
          return 0
        fi
        command getent "$@"
      }
      chgrp() { echo "chgrp $*" >&2; return 5; }
      main --user-mode --pg-bin-dir "${BINDIR:?}" --user-base-dir "${BASE:?}" \
        --pg-version 16 \
        --unix-socket-group pgclients \
        --destroy-db appdb --confirm-destroy-db appdb
        """,
        env={
            "BINDIR": str(bindir),
            "BASE": str(base),
            "CAP": str(cap),
            "SQLCAP": str(sqlcap),
        },
    )

    assert r.rc == 5
    assert "set socket dir group pgclients" in r.stderr
    assert not cap.exists()
    assert not sqlcap.exists()


@pytest.mark.unit
def test_user_mode_destroy_dry_run_does_not_create_layout(tmp_path, bash):
    base = tmp_path / "base"

    r = bash(
        """
      main --user-mode --user-base-dir "${BASE:?}" --destroy-db appdb --dry-run
        """,
        env={"BASE": str(base)},
    )

    assert r.rc == 0, r.stderr
    assert "Logical destroy manifest" in r.stdout
    assert "Provision dry-run manifest" in r.stdout
    assert not base.exists()
