import argparse
import os
import subprocess
from importlib import resources
from importlib import metadata as _md
from pathlib import Path


def _script_path(name: str) -> str:
    """Return the absolute path to a packaged shell helper script."""
    return str(resources.files("pgprovision._sh").joinpath(name))


def _user_mode_requested(passthrough_args) -> bool:
    """Return true when args or root-routing env request user-mode execution."""
    args = set(passthrough_args or [])
    if "--user-mode" in args:
        return True
    if os.environ.get("PGPROVISION_MODE", "").strip().lower() == "user":
        return True
    return os.environ.get("USER_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_file_requests_user_mode(passthrough_args) -> bool:
    """Return true when a forwarded env file requests user-mode root routing."""
    args = list(passthrough_args or [])
    for index, value in enumerate(args):
        if value != "--env-file" or index + 1 >= len(args):
            continue
        env_path = Path(args[index + 1])
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            normalized = raw_value.split("#", 1)[0].strip().strip("'\"").lower()
            if key == "PGPROVISION_MODE" and normalized == "user":
                return True
            if key == "USER_MODE" and normalized in {"1", "true", "yes", "on"}:
                return True
    return False


def _needs_root(passthrough_args):
    """Return true when a system-mode invocation needs sudo wrapping.

    User-mode never sudo-wraps. Help and dry-runs, including
    ``--uninstall-cluster --uninstall-only --dry-run`` previews, run without
    sudo; non-dry-run system uninstalls still sudo-wrap.
    """
    if os.geteuid() == 0:
        return False
    if _user_mode_requested(passthrough_args):
        return False
    if _env_file_requests_user_mode(passthrough_args):
        return False
    args = set(passthrough_args or [])
    return not ({"--help", "-h", "--dry-run"} & args)


def _run_script(script_rel: str, passthrough_args):
    """Run a packaged shell script, adding sudo only for system-mode actions."""
    script = _script_path(script_rel)
    base = ["/usr/bin/env", "bash", script] + list(passthrough_args or [])
    cmd = (["sudo", "-n", "--"] + base) if _needs_root(passthrough_args) else base
    # Preserve current env; let the bash scripts parse flags/env-files
    proc = subprocess.run(cmd)
    return proc.returncode


def main(argv=None):
    """CLI entry point that forwards provisioner flags to the shell backend."""
    # Passthrough CLI: we only parse a couple of meta-flags; everything else goes to the shell script.
    parser = argparse.ArgumentParser(
        prog="pgprovision",
        add_help=False,
        description="PostgreSQL idempotent provisioner",
    )
    # We don't duplicate the shell flags; we just forward them verbatim.
    parser.add_argument(
        "--help", "-h", action="store_true", help="Show shell script help"
    )
    parser.add_argument(
        "--version", action="store_true", help="Show package version and exit"
    )
    args, rest = parser.parse_known_args(argv)

    if args.version:
        ver = "unknown"
        for dist in ("pg-provision", "pgprovision"):
            try:
                ver = _md.version(dist)
                break
            except _md.PackageNotFoundError:
                continue
        print(ver)
        return 0

    if args.help or (argv is None and not rest):
        # Show the shell script's usage
        return _run_script("provision.sh", ["--help"])

    return _run_script("provision.sh", rest)
