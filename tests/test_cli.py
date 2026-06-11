import os
from types import SimpleNamespace

import pgprovision.cli as cli


class DummyProc(SimpleNamespace):
    def __init__(self, returncode=0):
        super().__init__(returncode=returncode)


def test_cli_no_sudo_for_help(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--help"])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_no_sudo_for_dry_run(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--dry-run"])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_no_sudo_for_uninstall_dry_run(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script(  # type: ignore[arg-type]
        "provision.sh", ["--uninstall-cluster", "--uninstall-only", "--dry-run"]
    )
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_uses_sudo_for_actions(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--repo", "pgdg"])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "sudo"


def test_cli_no_sudo_for_user_mode_action(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--user-mode", "--repo", "none"])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_no_sudo_for_env_file_user_mode_action(tmp_path, monkeypatch):
    calls = {}
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("PGPROVISION_MODE=user\n", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--env-file", str(env_file)])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_no_sudo_for_env_file_user_mode_with_inline_comment(tmp_path, monkeypatch):
    calls = {}
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("USER_MODE=true # user mode smoke\n", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        calls["cmd"] = cmd
        return DummyProc(0)

    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli._run_script("provision.sh", ["--env-file", str(env_file)])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]

    monkeypatch.setenv("PGPROVISION_MODE", "user")
    rc = cli._run_script("provision.sh", ["--repo", "none"])  # type: ignore[arg-type]
    assert rc == 0
    assert calls["cmd"][0] == "/usr/bin/env"
    assert "sudo" not in calls["cmd"]


def test_cli_rejects_destroy_with_uninstall(tmp_path, capfd):
    rc = cli.main(
        [
            "--destroy-db",
            "pgprov_test",
            "--uninstall-cluster",
            "--uninstall-only",
            "--dry-run",
            "--data-dir",
            str(tmp_path / "pgdata"),
        ]
    )
    captured = capfd.readouterr()

    assert rc == 2
    assert "uninstall and database/user destroy cannot be combined" in captured.err
