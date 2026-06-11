# uv user install (RHEL/Fedora) — FINAL REPORT

## Outcome

Local implementation is complete and verified for Phases 1-4, except for the required PR/main CI proof and the follow-up publish gate update. `publish.needs` remains `[pre-commit, unit, fedora-smoke, build]` by design because HC-4 forbids adding `fedora-user-mode-smoke` before a first green `main` run.

Phase 5 is deferred.

## Phase results

| Phase                     | Result                                   | Evidence                                                                                                                                       |
| ------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Docs                    | Pass                                     | `docs/run/uv-user-install-rhel/logs/phase-1-docs-local.log`                                                                                    |
| 2 CI pip elimination      | Code-green, PR CI pending                | `docs/run/uv-user-install-rhel/logs/phase-2-local-build-smoke.log`                                                                             |
| 3 Fedora user-mode smoke  | Local container pass, main proof pending | `docs/run/uv-user-install-rhel/logs/phase-3-workflow-audit.log`; `docs/run/uv-user-install-rhel/logs/phase-3-local-fedora-user-mode-smoke.log` |
| 4 Reference sweep         | Pass                                     | `docs/run/uv-user-install-rhel/logs/phase-4-reference-audit.log`; `docs/run/uv-user-install-rhel/logs/phase-4-full-local-gate.log`             |
| 5 Post-publish PyPI smoke | Deferred                                 | No tag publish occurred                                                                                                                        |

## Acceptance criteria

| Criterion                                                            | Status       | Evidence                                                                                                                                                                               |
| -------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| README Install uses `uv tool install pg-provision`; no pip user path | Pass         | `README.md`; `phase-1-docs-local.log`; `no-pip-user-path.sh`                                                                                                                           |
| README user-mode quick start follows uv install                      | Pass         | `README.md`                                                                                                                                                                            |
| `docs/test-plan-rhel.md` prerequisites and user-mode section use uv  | Pass         | `docs/test-plan-rhel.md`                                                                                                                                                               |
| `fedora-smoke` uses `uv tool install`; no pip in job                 | Pass locally | `.github/workflows/ci.yml`; `phase-2-local-build-smoke.log`                                                                                                                            |
| `build` wheel/sdist smokes use `uv tool install --force dist/*`      | Pass locally | `.github/workflows/ci.yml`; `phase-2-local-build-smoke.log`                                                                                                                            |
| `fedora-user-mode-smoke` exists                                      | Pass         | `.github/workflows/ci.yml`; `phase-3-workflow-audit.log`                                                                                                                               |
| `fedora-user-mode-smoke` passes on main                              | Blocked      | Requires commit/PR/merge and `gh run watch` after landing                                                                                                                              |
| `publish.needs` includes `fedora-user-mode-smoke`                    | Blocked      | Must wait until green `main` run per HC-4                                                                                                                                              |
| No `pip install pg-provision` in README or RHEL guide                | Pass         | `phase-4-reference-audit.log`; `no-pip-user-path.sh`                                                                                                                                   |
| Ubuntu CI jobs untouched; Ubuntu test plan untouched                 | Pass         | `docs/test-plan-ubuntu.md` diff empty; Ubuntu job blocks retain legacy pip                                                                                                             |
| Local gate passes                                                    | Pass         | `phase-4-full-local-gate.log`: `uv sync --dev`, `uv run pytest -q` (177 passed), `uv run pre-commit run --all-files`, `uv tool install --force .`, `pgprovision --user-mode --dry-run` |

## Notes

- The local Fedora 42 smoke runs user-mode provisioning as an unprivileged `pgprovci` user. Root is used only for container package installation.
- The audit script is job-aware: it rejects pip installs outside the frozen Ubuntu workflow jobs while preserving those Ubuntu blocks unchanged.
- The required all-files pre-commit gate formatted pre-existing markdown and graphify artifacts outside the main docs/CI slice. Those non-semantic hook changes remain in the worktree because reverting them makes the mandated gate fail.
