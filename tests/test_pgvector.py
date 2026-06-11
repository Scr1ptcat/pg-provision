"""
pgvector package and extension initialization behavior tests.
"""

import textwrap

import pytest


def _write_executable(path, body):
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _fake_pg_bin(tmp_path, psql_body=None):
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name in ["postgres", "psql", "initdb", "pg_ctl"]:
        body = """\
        #!/usr/bin/env bash
        exit 0
        """
        _write_executable(bindir / name, body)
    if psql_body is not None:
        _write_executable(bindir / "psql", psql_body)
    return bindir


def _make_extension_control(bindir, control):
    extension_dir = bindir.parent / "share" / "extension"
    extension_dir.mkdir(parents=True, exist_ok=True)
    (extension_dir / f"{control}.control").write_text(
        "comment = 'test'\n", encoding="utf-8"
    )


@pytest.mark.unit
def test_pgvector_flag_triggers_create_extension(tmp_path, bash):
    """
    INIT_PGVECTOR=true should create the vector extension in the target DB.
    """
    cap = tmp_path / "cap.txt"
    env = {"INIT_PGVECTOR": "true", "PGVECTOR_DB": "vecdb", "CAP": str(cap)}
    script = r"""
      CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 0; }
      conditionally_init_pgvector
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr

    out = r.stdout
    assert "sudo -u postgres" in out
    assert "-d vecdb" in out
    assert "CREATE EXTENSION IF NOT EXISTS vector" in out


@pytest.mark.unit
def test_pgvector_targets_create_db_by_default(tmp_path, bash):
    """
    Without --pgvector-db, the create-db target is used.
    """
    cap = tmp_path / "cap.txt"
    env = {"INIT_PGVECTOR": "true", "CREATE_DB": "createdb", "CAP": str(cap)}
    script = r"""
      CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 0; }
      conditionally_init_pgvector
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr
    assert "-d createdb" in r.stdout


@pytest.mark.unit
def test_pgvector_pgvector_db_overrides_target(tmp_path, bash):
    """
    PGVECTOR_DB overrides CREATE_DB for extension initialization.
    """
    cap = tmp_path / "cap.txt"
    env = {
        "INIT_PGVECTOR": "true",
        "CREATE_DB": "createdb",
        "PGVECTOR_DB": "vecdb",
        "CAP": str(cap),
    }
    script = r"""
      CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 0; }
      conditionally_init_pgvector
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr
    assert "-d vecdb" in r.stdout
    assert "-d createdb" not in r.stdout


@pytest.mark.unit
def test_pgvector_absent_does_not_invoke(tmp_path, bash):
    """
    Without INIT_PGVECTOR=true, no psql invocation occurs.
    """
    cap = tmp_path / "cap.txt"
    env = {"CAP": str(cap)}
    script = r"""
      CAP="${CAP:?}"
      : > "$CAP"
      sudo() { echo "sudo $*" >> "$CAP"; return 0; }
      conditionally_init_pgvector
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr
    assert r.stdout.strip() == ""


@pytest.mark.unit
def test_pgvector_package_names_ubuntu_and_rhel(bash):
    """
    System backends should install the PGDG pgvector package for the active major.
    """
    ubuntu = bash(
        """
      run() { echo "$*"; }
      OS_FAMILY=ubuntu
      PG_VERSION=18
      REPO_KIND=pgdg
      INIT_PGVECTOR=true
      SUDO=()
      load_os_module
      os_install_extension_packages
        """
    )
    assert ubuntu.rc == 0, ubuntu.stderr
    assert "postgresql-18-pgvector" in ubuntu.stdout

    rhel = bash(
        """
      _pkgmgr() { echo dnf; }
      run() { echo "$*"; "$@"; }
      dnf() { echo "dnf $*"; }
      OS_FAMILY=rhel
      PG_VERSION=18
      REPO_KIND=pgdg
      INIT_PGVECTOR=true
      SUDO=()
      load_os_module
      os_install_extension_packages
        """
    )
    assert rhel.rc == 0, rhel.stderr
    assert "pgvector_18" in rhel.stdout


@pytest.mark.unit
def test_pgvector_repo_os_fails_fast(bash):
    """
    pgvector is only supported through the verified PGDG package paths.
    """
    r = bash(
        """
      OS_FAMILY=ubuntu
      PG_VERSION=18
      REPO_KIND=os
      INIT_PGVECTOR=true
      SUDO=()
      load_os_module
      os_install_extension_packages
        """
    )
    assert r.rc == 2
    assert "requires --repo pgdg" in r.stderr


@pytest.mark.unit
def test_pgvector_user_mode_requires_control_file(tmp_path, bash):
    bindir = _fake_pg_bin(tmp_path)

    r = bash(
        """
      OS_FAMILY=user
      PG_VERSION=16
      PG_BIN_DIR="${BINDIR:?}"
      INIT_PGVECTOR=true
      load_os_module
      os_install_extension_packages
        """,
        env={"BINDIR": str(bindir)},
    )

    assert r.rc == 2
    assert "User-mode pgvector requested" in r.stderr
    assert "vector.control" in r.stderr
    assert "MVP" not in r.stderr


@pytest.mark.unit
def test_pgvector_user_mode_uses_runtime_psql_without_sudo(tmp_path, bash):
    cap = tmp_path / "psql.log"
    bindir = _fake_pg_bin(
        tmp_path,
        psql_body="""\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "${CAP:?}"
        exit 0
        """,
    )
    _make_extension_control(bindir, "vector")

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
      INIT_PGVECTOR=true
      PGVECTOR_DB=vecdb
      load_os_module
      os_install_extension_packages
      conditionally_init_pgvector
      cat "${CAP:?}"
        """,
        env={"BINDIR": str(bindir), "RUNTIME": str(tmp_path / "run"), "CAP": str(cap)},
    )

    assert r.rc == 0, r.stderr
    assert "sudo" not in r.stdout
    assert f"-h {tmp_path / 'run'}" in r.stdout
    assert "-d vecdb" in r.stdout
    assert "-U appuser" in r.stdout
    assert "CREATE EXTENSION IF NOT EXISTS vector" in r.stdout


@pytest.mark.unit
def test_load_os_module_requires_extension_package_hook(tmp_path, bash):
    """
    load_os_module should reject backends missing the extension package hook.
    """
    os_dir = tmp_path / "os"
    os_dir.mkdir()
    backend = os_dir / "fake.sh"
    backend.write_text(
        "\n".join(
            [
                "os_prepare_repos() { :; }",
                "os_install_packages() { :; }",
                "os_init_cluster() { :; }",
                "os_get_paths() { :; }",
                "os_restart() { :; }",
            ]
        ),
        encoding="utf-8",
    )
    env = {"FAKE_SCRIPT_DIR": str(tmp_path)}
    r = bash(
        """
      SCRIPT_DIR="$FAKE_SCRIPT_DIR"
      OS_FAMILY=fake
      load_os_module
        """,
        env=env,
    )
    assert r.rc == 2
    assert "os_install_extension_packages" in r.stderr
