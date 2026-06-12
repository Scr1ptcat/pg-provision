import hashlib
import tarfile
import textwrap

import pytest


def _write_executable(path, body):
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _make_fake_pg_tarball(tmp_path, major="16", missing=()):
    root = tmp_path / "postgresql-16"
    bindir = root / "bin"
    bindir.mkdir(parents=True)
    for name in ["postgres", "initdb", "pg_ctl", "psql"]:
        if name in missing:
            continue
        _write_executable(
            bindir / name,
            f"""\
            #!/usr/bin/env bash
            if [[ "${{1:-}}" == "--version" ]]; then
              echo "{name} (PostgreSQL) {major}.1"
              exit 0
            fi
            exit 0
            """,
        )
    tarball = tmp_path / "postgresql.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(root, arcname=root.name)
    sha256 = hashlib.sha256(tarball.read_bytes()).hexdigest()
    return tarball, sha256


def _nonroot_id_stub():
    return """\
      id() {
        case "${1:-}" in
          -u) echo 1000 ;;
          -un) echo appuser ;;
          *) command id "$@" ;;
        esac
      }
    """


@pytest.mark.unit
def test_bootstrap_requires_sha256_for_url(bash):
    r = bash(
        f"""
      {_nonroot_id_stub()}
      main --user-mode --bootstrap-tarball https://example.invalid/postgresql.tar.gz --bootstrap-only
        """
    )

    assert r.rc == 2
    assert "--bootstrap-sha256" in r.stderr
    assert "required" in r.stderr


@pytest.mark.unit
def test_bootstrap_requires_sha256_for_local_file(tmp_path, bash):
    tarball = tmp_path / "postgresql.tar.gz"
    tarball.write_bytes(b"not a real tarball")

    r = bash(
        f"""
      {_nonroot_id_stub()}
      main --user-mode --bootstrap-tarball "${{TARBALL:?}}" --bootstrap-only
        """,
        env={"TARBALL": str(tarball)},
    )

    assert r.rc == 2
    assert "--bootstrap-sha256" in r.stderr
    assert "including local files" in r.stderr


@pytest.mark.unit
def test_bootstrap_rejects_checksum_mismatch(tmp_path, bash):
    tarball, sha256 = _make_fake_pg_tarball(tmp_path)
    wrong_sha256 = ("0" if sha256[0] != "0" else "1") + sha256[1:]

    r = bash(
        f"""
      {_nonroot_id_stub()}
      main --user-mode \
        --bootstrap-tarball "${{TARBALL:?}}" \
        --bootstrap-sha256 "${{SHA256:?}}" \
        --bootstrap-dir "${{BOOTDIR:?}}" \
        --bootstrap-only
        """,
        env={
            "TARBALL": str(tarball),
            "SHA256": wrong_sha256,
            "BOOTDIR": str(tmp_path / "cache"),
        },
    )

    assert r.rc == 2
    assert "checksum mismatch" in r.stderr


@pytest.mark.unit
def test_bootstrap_extracts_bin_dir(tmp_path, bash):
    tarball, sha256 = _make_fake_pg_tarball(tmp_path)
    bootdir = tmp_path / "cache"

    r = bash(
        """
      RUNTIME_REQUESTED_MODE=user
      PG_VERSION=16
      PGPROVISION_BOOTSTRAP_TARBALL="${TARBALL:?}"
      PGPROVISION_BOOTSTRAP_SHA256="${SHA256:?}"
      PGPROVISION_BOOTSTRAP_DIR="${BOOTDIR:?}"
      bootstrap_apply_if_requested
      printf 'PG_BIN_DIR=%s\n' "$PG_BIN_DIR"
      test -x "$PG_BIN_DIR/postgres"
      test -x "$PG_BIN_DIR/initdb"
      test -x "$PG_BIN_DIR/pg_ctl"
      test -x "$PG_BIN_DIR/psql"
        """,
        env={"TARBALL": str(tarball), "SHA256": sha256, "BOOTDIR": str(bootdir)},
    )

    expected = bootdir / "16" / sha256 / "root" / "postgresql-16" / "bin"
    assert r.rc == 0, r.stderr
    assert f"PG_BIN_DIR={expected}" in r.stdout


@pytest.mark.unit
def test_bootstrap_validates_required_binaries(tmp_path, bash):
    tarball, sha256 = _make_fake_pg_tarball(tmp_path, missing={"pg_ctl"})

    r = bash(
        f"""
      {_nonroot_id_stub()}
      main --user-mode \
        --bootstrap-tarball "${{TARBALL:?}}" \
        --bootstrap-sha256 "${{SHA256:?}}" \
        --bootstrap-dir "${{BOOTDIR:?}}" \
        --bootstrap-only
        """,
        env={
            "TARBALL": str(tarball),
            "SHA256": sha256,
            "BOOTDIR": str(tmp_path / "cache"),
        },
    )

    assert r.rc == 2
    assert "required PostgreSQL binaries" in r.stderr
    assert "pg_ctl" in r.stderr


@pytest.mark.unit
def test_bootstrap_only_exits_before_provision(tmp_path, bash):
    tarball, sha256 = _make_fake_pg_tarball(tmp_path)

    r = bash(
        f"""
      {_nonroot_id_stub()}
      sudo() {{ echo "sudo called"; return 99; }}
      os_detect() {{ echo "os_detect called"; return 99; }}
      load_os_module() {{ echo "load_os_module called"; return 99; }}
      main --user-mode --pg-version 16 \
        --bootstrap-tarball "${{TARBALL:?}}" \
        --bootstrap-sha256 "${{SHA256:?}}" \
        --bootstrap-dir "${{BOOTDIR:?}}" \
        --bootstrap-only
        """,
        env={
            "TARBALL": str(tarball),
            "SHA256": sha256,
            "BOOTDIR": str(tmp_path / "cache"),
        },
    )

    assert r.rc == 0, r.stderr
    assert "Using bootstrapped PostgreSQL binaries" in r.stdout
    assert "os_detect called" not in r.stdout
    assert "load_os_module called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_bootstrap_rejects_system_mode(tmp_path, bash):
    tarball, sha256 = _make_fake_pg_tarball(tmp_path)

    r = bash(
        """
      main --bootstrap-tarball "${TARBALL:?}" \
        --bootstrap-sha256 "${SHA256:?}" \
        --bootstrap-dir "${BOOTDIR:?}" \
        --bootstrap-only
        """,
        env={
            "TARBALL": str(tarball),
            "SHA256": sha256,
            "BOOTDIR": str(tmp_path / "cache"),
        },
    )

    assert r.rc == 2
    assert "requires --user-mode" in r.stderr
