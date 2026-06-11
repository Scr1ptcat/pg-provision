import os

import pytest


@pytest.mark.unit
def test_runtime_system_psql_uses_sudo_u_postgres(tmp_path, bash):
    cap = tmp_path / "sudo.txt"

    r = bash(
        """
      export CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 0; }
      PORT=5544
      runtime_psql postgres -c "SELECT 1;"
      cat "$CAP"
        """,
        env={"CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "sudo -u postgres psql" in r.stdout
    assert "-p 5544" in r.stdout
    assert "-d postgres" in r.stdout


@pytest.mark.unit
def test_runtime_user_psql_does_not_use_sudo(tmp_path, bash):
    cap = tmp_path / "psql.txt"
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    psql = bindir / "psql"
    psql.write_text(
        '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "${CAP:?}"\n',
        encoding="utf-8",
    )
    psql.chmod(0o755)

    r = bash(
        """
      export CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 99; }
      id() { if [[ "${1:-}" == "-un" ]]; then echo appuser; else command id "$@"; fi; }
      runtime_init user false
      PG_BIN_DIR="${BINDIR:?}"
      UNIX_SOCKET_DIR="${SOCKET:?}"
      PORT=55432
      PGUSER=postgres
      runtime_psql postgres -c "SELECT 1;"
      cat "$CAP"
        """,
        env={"CAP": str(cap), "BINDIR": str(bindir), "SOCKET": str(tmp_path / "run")},
    )

    assert r.rc == 0, r.stderr
    assert "sudo" not in r.stdout
    assert f"-h {tmp_path / 'run'}" in r.stdout
    assert "-p 55432" in r.stdout
    assert "-U appuser" in r.stdout
    assert "-U postgres" not in r.stdout


@pytest.mark.unit
def test_runtime_user_mode_rejects_root_non_dry_run(bash):
    r = bash(
        """
      id() { if [[ "${1:-}" == "-u" ]]; then echo 0; else command id "$@"; fi; }
      runtime_init user false
        """
    )

    assert r.rc == 2
    assert "must be run as the target non-root OS user" in r.stderr


@pytest.mark.unit
def test_runtime_dry_run_records_without_executing(tmp_path, bash):
    cap = tmp_path / "ran.txt"
    target = tmp_path / "would-write.conf"

    r = bash(
        """
      CAP="${CAP:?}"
      TARGET="${TARGET:?}"
      : > "$CAP"
      dangerous() { echo "ran" >> "$CAP"; }
      runtime_init system true
      runtime_elevate dangerous --flag
      runtime_write_file_atomic "$TARGET" "0600" "" "" <<< "content"
      runtime_manifest_print
      [[ ! -e "$TARGET" ]]
      [[ ! -s "$CAP" ]]
        """,
        env={"CAP": str(cap), "TARGET": str(target)},
    )

    assert r.rc == 0, r.stderr
    assert "action: exec" in r.stdout
    assert "dangerous --flag" in r.stdout
    assert "action: write_file" in r.stdout
    assert str(target) in r.stdout
    assert not target.exists()
    assert cap.read_text(encoding="utf-8") == ""


@pytest.mark.unit
def test_dry_run_skips_self_heal_and_backend_mutations(bash):
    r = bash(
        """
      os_detect() { OS_FAMILY=ubuntu; echo "os_detect"; }
      load_os_module() {
        echo "load_os_module"
        os_self_heal() { echo "os_self_heal called"; return 99; }
        os_prepare_repos() { echo "os_prepare_repos called"; return 99; }
        os_install_packages() { echo "os_install_packages called"; return 99; }
        os_install_extension_packages() { echo "os_install_extension_packages called"; return 99; }
        os_init_cluster() { echo "os_init_cluster called"; return 99; }
        os_restart() { echo "os_restart called"; return 99; }
      }
      apply_dropin_config() { echo "apply_dropin_config called"; return 99; }
      apply_hba_policy() { echo "apply_hba_policy called"; return 99; }
      write_pg_ident_map() { echo "write_pg_ident_map called"; return 99; }
      conditionally_init_pg_stat_statements() { echo "pgss called"; return 99; }
      conditionally_init_pgvector() { echo "pgvector called"; return 99; }
      create_db_and_user() { echo "create_db_and_user called"; return 99; }
      write_stamp() { echo "write_stamp called"; return 99; }
      main --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Provision dry-run manifest" in r.stdout
    assert "os_detect" in r.stdout
    assert "load_os_module" in r.stdout
    for forbidden in [
        "os_self_heal called",
        "os_prepare_repos called",
        "os_install_packages called",
        "os_install_extension_packages called",
        "os_init_cluster called",
        "os_restart called",
        "apply_dropin_config called",
        "apply_hba_policy called",
        "write_pg_ident_map called",
        "pgss called",
        "pgvector called",
        "create_db_and_user called",
        "write_stamp called",
    ]:
        assert forbidden not in r.stdout


@pytest.mark.unit
def test_runtime_write_file_atomic_preserves_mode(tmp_path, bash):
    target = tmp_path / "postgresql.conf"
    target.write_text("old\n", encoding="utf-8")
    os.chmod(target, 0o640)

    r = bash(
        """
      TARGET="${TARGET:?}"
      printf '%s\\n' "new" | runtime_write_file_atomic "$TARGET" "" "" ""
      stat -c '%a' "$TARGET"
      cat "$TARGET"
        """,
        env={"TARGET": str(target)},
    )

    assert r.rc == 0, r.stderr
    assert "640" in r.stdout.splitlines()
    assert target.read_text(encoding="utf-8") == "new\n"


@pytest.mark.unit
def test_runtime_resolves_pg_bin_dir(tmp_path, bash):
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    psql = bindir / "psql"
    psql.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    psql.chmod(0o755)

    r = bash(
        """
      PG_VERSION=999
      unset PG_BIN_DIR
      export PATH="${BINDIR:?}:$PATH"
      runtime_resolve_pg_bin
        """,
        env={"BINDIR": str(bindir)},
    )

    assert r.rc == 0, r.stderr
    assert r.stdout.strip() == str(bindir)


@pytest.mark.unit
def test_runtime_resolve_prefers_postgres_binary_dir_over_psql_only_dir(tmp_path, bash):
    psql_only = tmp_path / "psql-only"
    full_bin = tmp_path / "full-bin"
    psql_only.mkdir()
    full_bin.mkdir()
    for path in [psql_only / "psql", full_bin / "psql", full_bin / "postgres"]:
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)

    r = bash(
        """
      PG_VERSION=999
      unset PG_BIN_DIR
      export PATH="${PSQL_ONLY:?}:${FULL_BIN:?}:$PATH"
      runtime_resolve_pg_bin
        """,
        env={"PSQL_ONLY": str(psql_only), "FULL_BIN": str(full_bin)},
    )

    assert r.rc == 0, r.stderr
    assert r.stdout.strip() == str(full_bin)


@pytest.mark.unit
def test_assert_psql_major_uses_pg_bin_dir(tmp_path, bash):
    bindir = tmp_path / "pgbin"
    path_psql = tmp_path / "path-psql"
    bindir.mkdir()
    path_psql.mkdir()
    pgbin_psql = bindir / "psql"
    path_psql_bin = path_psql / "psql"
    pgbin_psql.write_text(
        "#!/bin/sh\necho 'psql (PostgreSQL) 16.1'\n", encoding="utf-8"
    )
    path_psql_bin.write_text(
        "#!/bin/sh\necho 'psql (PostgreSQL) 18.3'\n", encoding="utf-8"
    )
    pgbin_psql.chmod(0o755)
    path_psql_bin.chmod(0o755)

    r = bash(
        """
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      export PATH="${PATH_PSQL:?}:$PATH"
      assert_psql_major_matches
        """,
        env={"BINDIR": str(bindir), "PATH_PSQL": str(path_psql)},
    )

    assert r.rc == 0, r.stderr


@pytest.mark.unit
def test_load_os_module_requires_self_heal_after_phase4(tmp_path, bash):
    os_dir = tmp_path / "os"
    os_dir.mkdir()
    backend = os_dir / "fake.sh"
    backend.write_text(
        "\n".join(
            [
                "os_prepare_repos() { :; }",
                "os_install_packages() { :; }",
                "os_install_extension_packages() { :; }",
                "os_init_cluster() { :; }",
                "os_get_paths() { :; }",
                "os_restart() { :; }",
            ]
        ),
        encoding="utf-8",
    )

    r = bash(
        """
      SCRIPT_DIR="$FAKE_SCRIPT_DIR"
      OS_FAMILY=fake
      load_os_module
        """,
        env={"FAKE_SCRIPT_DIR": str(tmp_path)},
    )

    assert r.rc == 2
    assert "os_self_heal" in r.stderr
