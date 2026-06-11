import shutil
import pytest


@pytest.mark.unit
def test_is_valid_pgdata_accepts_symlinked_wal(tmp_path, bash):
    # Arrange: build a minimal, valid PGDATA with symlinked pg_wal
    pg = tmp_path / "pgdata"
    (pg / "global").mkdir(parents=True)
    (pg / "base").mkdir()
    (pg / "global" / "pg_control").write_bytes(b"X")
    (pg / "PG_VERSION").write_text("16\n", encoding="utf-8")
    wal = tmp_path / "wal"
    wal.mkdir()
    (pg / "pg_wal").symlink_to(wal)

    script = f"""
      OS_FAMILY=ubuntu; PG_VERSION=16; load_os_module
      _is_valid_pgdata "{pg}"
      echo RC=$?
    """
    r = bash(script)
    assert r.rc == 0, r.stderr
    assert "RC=0" in r.stdout  # success


@pytest.mark.unit
@pytest.mark.parametrize("osfam", ["rhel", "ubuntu"])
@pytest.mark.parametrize("missing", ["PG_VERSION", "global/pg_control", "base"])
def test_is_valid_pgdata_fails_when_core_piece_missing(tmp_path, bash, osfam, missing):
    pg = tmp_path / "pgdata"
    (pg / "global").mkdir(parents=True)
    (pg / "base").mkdir()
    (pg / "PG_VERSION").write_text("16\n", encoding="utf-8")
    (pg / "global" / "pg_control").write_bytes(b"X")
    (pg / "pg_wal").mkdir()
    # Remove the one we want missing
    if missing == "PG_VERSION":
        (pg / "PG_VERSION").unlink()
    elif missing == "global/pg_control":
        (pg / "global" / "pg_control").unlink()
    elif missing == "base":
        shutil.rmtree(pg / "base")

    script = f"""
      OS_FAMILY={osfam}; PG_VERSION=16; load_os_module
      if _is_valid_pgdata "{pg}"; then echo RC=0; else echo RC=$?; fi
    """

    r = bash(script)
    assert r.rc == 0, r.stderr
    assert "RC=1" in r.stdout  # failure


@pytest.mark.unit
def test_ubuntu_relocation_refuses_to_drop_valid_pgdata(tmp_path, bash):
    current = tmp_path / "current"
    target = tmp_path / "target"
    (current / "global").mkdir(parents=True)
    (current / "base").mkdir()
    (current / "pg_wal").mkdir()
    (current / "global" / "pg_control").write_bytes(b"X")
    (current / "PG_VERSION").write_text("16\n", encoding="utf-8")

    for name in ["pg_dropcluster", "pg_createcluster"]:
        stub = tmp_path / name
        stub.write_text(
            f'#!/bin/sh\necho {name.upper()}_CALLED "$@"\nexit 0\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)

    r = bash(
        """
      export PATH="${STUBDIR:?}:$PATH"
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=()
      pg_lsclusters() {
        printf '16 main online 5432 postgres %s log\\n' "${CURRENT:?}"
      }
      os_stop() { echo "STOP_CALLED"; return 0; }
      load_os_module
      os_init_cluster "$TARGET"
        """,
        env={"STUBDIR": str(tmp_path), "CURRENT": str(current), "TARGET": str(target)},
    )

    assert r.rc == 2
    assert "Refusing to relocate" in r.stderr
    assert "valid PGDATA" in r.stderr
    assert "uninstall/remove flags" in r.stderr
    assert "PG_DROPCLUSTER_CALLED" not in r.stdout
    assert "PG_CREATECLUSTER_CALLED" not in r.stdout


@pytest.mark.unit
def test_ubuntu_relocation_uses_elevated_pgdata_validation(tmp_path, bash):
    current = tmp_path / "current"
    target = tmp_path / "target"
    (current / "global").mkdir(parents=True)
    (current / "base").mkdir()
    (current / "pg_wal").mkdir()
    (current / "global" / "pg_control").write_bytes(b"X")
    (current / "PG_VERSION").write_text("16\n", encoding="utf-8")

    for name in ["pg_dropcluster", "pg_createcluster"]:
        stub = tmp_path / name
        stub.write_text(
            f'#!/bin/sh\necho {name.upper()}_CALLED "$@"\nexit 0\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)

    r = bash(
        """
      export PATH="${STUBDIR:?}:$PATH"
      OS_FAMILY=ubuntu
      PG_VERSION=16
      SUDO=(sudo -n)
      pg_lsclusters() {
        printf '16 main online 5432 postgres %s log\\n' "${CURRENT:?}"
      }
      os_stop() { echo "STOP_CALLED"; return 0; }
      load_os_module
      _is_valid_pgdata() { return 1; }
      os_init_cluster "$TARGET"
        """,
        env={"STUBDIR": str(tmp_path), "CURRENT": str(current), "TARGET": str(target)},
    )

    assert r.rc == 2
    assert "Refusing to relocate" in r.stderr
    assert "valid PGDATA" in r.stderr
    assert "PG_DROPCLUSTER_CALLED" not in r.stdout
