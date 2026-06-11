# uv Migration Plan

## Purpose

Migrate contributor workflows and CI from ad hoc `pip install` steps to a single **uv**-based path (`uv sync`, `uv run`, `uv build`) with a committed lockfile, while preserving the **end-user PyPI install story** (`pip install pg-provision`) and the existing **setuptools + setuptools-scm** build backend. Align publish gates with the operator's **Fedora/RHEL-first** platform priority by replacing Rocky smoke with Fedora container coverage and removing Ubuntu integration jobs from `publish.needs`.

## Facts

### Investigation checklist (FACT / NOT FOUND)

1. **`pyproject.toml` today** — **FACT:** Build backend is setuptools + setuptools-scm (`pyproject.toml:L1-L3`, `L57-L58`). `[project]` declares no runtime `dependencies` (`pyproject.toml:L5-L26`). No `[project.optional-dependencies]`, no PEP 735 `[dependency-groups]`, no `[tool.uv]` block. Pytest config only under `[tool.pytest.ini_options]` (`pyproject.toml:L53-L55`). Console script: `pgprovision = "pgprovision.cli:main"` (`pyproject.toml:L28-L29`).

2. **`uv.lock`** — **FACT:** File exists on disk but is **untracked** (`git ls-files uv.lock` empty; `git status` shows `?? uv.lock`). Current contents are a minimal stub: lock format v1, `requires-python = ">=3.9"`, single editable `pg-provision` package entry — **no dev dependency pins** (`uv.lock:L1-L8`).

3. **CI jobs that install Python packages** — **FACT:**

   | Job | Install pattern | Citations |
   | --- | --- | --- |
   | `pre-commit` | No direct pip; `pre-commit/action@v3.0.1` manages hook envs | `.github/workflows/ci.yml:L20-L32` |
   | `unit` | `pip install -U pytest build twine`; `pip install .` for smoke | `.github/workflows/ci.yml:L51-L65` |
   | `rocky-smoke` | `python3 -m pip install .` in `rockylinux:9` container | `.github/workflows/ci.yml:L109-L117` |
   | `build` | `pip install build twine`; `python -m build`; `pip install dist/*` | `.github/workflows/ci.yml:L145-L170` |
   | `integration-ubuntu-smoke` | `pip install .` | `.github/workflows/ci.yml:L199-L202` |
   | `user-mode-smoke` | `pip install .` | `.github/workflows/ci.yml:L235-L238` |
   | `integration-ubuntu-destructive` | `pip install .` | `.github/workflows/ci.yml:L313-L316` |
   | `publish` | `pip install build`; `python -m build` | `.github/workflows/ci.yml:L374-L378` |

   All jobs use `actions/setup-python@v5`; several set `cache: 'pip'` (`.github/workflows/ci.yml:L29`, `L50`, `L144`, etc.).

4. **`publish.needs`** — **FACT:** `needs: [pre-commit, unit, rocky-smoke, build, integration-ubuntu-smoke, user-mode-smoke]` (`.github/workflows/ci.yml:L358`). `integration-ubuntu-destructive` is **not** in `publish.needs` (`.github/workflows/ci.yml:L292-L294` vs `L355-L358`).

5. **`.pre-commit-config.yaml` Python assumptions** — **FACT:** Default Python is `python3` (`/.pre-commit-config.yaml:L13-L14`). Local `pytest` hook uses `language: python` with `entry: pytest -q` and `additional_dependencies: [pytest]` — an **isolated mini-env**, not the project venv (`.pre-commit-config.yaml:L76-L84`). Ruff, Black, shellcheck, etc. use their own pinned hook envs.

6. **`tests/conftest.py` install requirement** — **FACT:** Inserts `src/` on `sys.path`; unit tests do **not** require editable install (`tests/conftest.py:L20-L23`). CLI smoke tests in CI currently use `pip install .` then `pgprovision` on PATH.

7. **Docs/prompts hard-coding pip or hybrid uv+pip** — **FACT:**
   - End-user: `pip install pg-provision` in `README.md:L9-L11`, `docs/test-plan-rhel.md:L13`.
   - Contributor: `docs/pre-commit.md:L14-L15` recommends `pipx`/`pip install pre-commit`.
   - Live validation in plans: `python -m pip install -e .` (`docs/plans/phases-8-9-completion-plan.md:L163`, `docs/plans/phases-8-9-uninstall-ci-plan.md:L264`).
   - Orchestrator prompts: `uv run python -m pip install -e .` (`docs/prompts/2026-06-11-phases-8-9-completion-orchestrator.md:L7`, `docs/prompts/2026-06-10-phases-8-9-uninstall-ci-orchestrator.md:L7`).
   - Recent run artifacts confirm local gates already use `uv run pytest -q` and `uv run pre-commit run --all-files` (`docs/run/phases-8-9-completion/LEDGER.md:L6-L11`).

8. **Minimum Fedora/RHEL CI matrix for operator priority** — **FACT (current):** Publish gates include `rocky-smoke` (Rocky 9 container dry-run) plus two Ubuntu PGDG integration smokes (`README.md:L286-L297`). No Fedora container job exists. RHEL full integration documented as manual/self-hosted only (`README.md:L295`). Separate workflow `.github/workflows/pre-commit.yml` mirrors pre-commit on PR/push (`/.github/workflows/pre-commit.yml:L1-L18`).

9. **Rocky container job handling** — **FACT:** `rocky-smoke` runs on `ubuntu-latest` with `container: rockylinux:9`, installs git/python3/pip via dnf, sets `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION` for shallow/versionless installs (`.github/workflows/ci.yml:L90-L117`).

10. **`uv build` vs `python -m build`** — **FACT:** `uv build` succeeds locally (uv 0.11.14), producing sdist + wheel under `-o`. Artifacts include expected package layout (`pgprovision/_sh/*.sh`, console entry). `twine` is not yet declared as a dev dep (no lock entry). Sdist currently bundles repo extras (e.g. `graphify-out/`, `docs/run/`) via setuptools-scm git archive — **pre-existing packaging surface**, not introduced by uv.

### Additional facts

- **Zero runtime Python dependencies** — confirmed by absence of `[project.dependencies]` (`pyproject.toml:L5-L26`).
- **`.python-version`** — **NOT FOUND** in repo root.
- **`.gitignore`** ignores `.venv/` only; does **not** ignore `uv.lock` (`.gitignore:L11`).
- **Fedora PGDG repo URL bug (related follow-up):** RHEL backend uses `rel="$(rpm -E %rhel)"` for PGDG RPM URL (`src/pgprovision/_sh/os/rhel.sh:L235-L239`). On Fedora, `%rhel` does not expand; PGDG expects `F-<version>-<arch>` / `pgdg-fedora-repo-latest.noarch.rpm`. **Out of scope** for this migration unless Fedora container smoke is extended to PGDG integration (recommended: dry-run only until fixed).

## Inferences

- Declaring dev deps in `[dependency-groups]` and running `uv lock` will replace the stub lockfile with pinned pytest/build/twine/pre-commit versions; contributors get reproducible envs without changing runtime packaging.
- Unit tests can keep running without install thanks to `conftest.py`; CLI smokes should use **`uv sync` + `uv run pgprovision`** on ubuntu-hosted jobs (editable install from sync) and **`pip install` of built wheel** on Fedora/RHEL-family container smokes to validate the end-user install path.
- Replacing `pre-commit/action` with `uv run pre-commit` after `uv sync` ensures CI uses the same hook versions as local dev; the local `pytest` hook should switch to `uv run pytest -q` (`language: system`) so it uses the locked project env instead of an isolated pytest-only env.
- Removing Ubuntu integration jobs from `publish.needs` reduces PGDG apt flake risk on release tags; Ubuntu jobs can remain as **non-gating** `workflow_dispatch` / `schedule` targets for upstream compatibility without blocking the operator's Fedora/RHEL workflow.
- `uv build` is a drop-in replacement for `python -m build` for this setuptools backend; publish can upload the same `dist/` artifacts via `gh-action-pypi-publish`.
- Fedora container dry-run smoke catches RHEL-family packaging/`importlib.resources` issues similar to today's Rocky job; it does **not** validate PGDG repo wiring until the `%rhel` follow-up lands.
- Sdist bloat (non-runtime files in tarball) predates uv migration; fixing `MANIFEST.in`/setuptools-scm config is a separate packaging hygiene task, not a uv blocker.

## Scope

### In Scope

| Item | Detail |
| --- | --- |
| Dev dependency declaration | PEP 735 `[dependency-groups]` (dev: pytest, build, twine, pre-commit) |
| Lockfile policy | Generate and **commit** `uv.lock` |
| Local contributor path | Document `uv sync`, `uv run pytest`, `uv run pre-commit`, `uv build`, `uv run pgprovision` |
| CI tool migration | `astral-sh/setup-uv` + `uv sync` + `uv run`/`uv build` on ubuntu-hosted jobs |
| Publish job | `uv build` before `gh-action-pypi-publish`; preserve OIDC trusted publishing |
| OS smoke realignment | Replace `rocky-smoke` with **Fedora** container dry-run; update `publish.needs` |
| Ubuntu job demotion | Remove `integration-ubuntu-smoke` and `user-mode-smoke` from `publish.needs`; gate with `workflow_dispatch` / `schedule` only |
| Docs | Contributor section in README; rewrite `docs/pre-commit.md`; update plan/orchestrator gate commands |
| Pre-commit hook | Local pytest hook uses project uv env |
| `.python-version` | Pin default interpreter (3.13) for uv |

### Out of Scope

| Item | Reason |
| --- | --- |
| Build backend change (Poetry/hatch/pdm) | setuptools works with `uv build`; zero runtime deps |
| Requiring end users to install uv | PyPI `pip install` remains documented |
| Shell provisioning / OS backend rewrites | Workflow-only migration |
| Fedora PGDG `%rhel` fix | Related follow-up; blocks PGDG integration smoke on Fedora, not dry-run smoke |
| Self-hosted RHEL runner provisioning | Document manual dispatch; no infra in this plan |
| Sdist content pruning (`graphify-out/`, etc.) | Pre-existing; separate packaging task |
| Ubuntu as primary publish gate | Operator priority is Fedora/RHEL |

## Requirements

1. **Dev dependencies** — Add `[dependency-groups.dev]` with pinned-generation via `uv lock` containing at minimum: `pytest`, `build`, `twine`, `pre-commit`. No runtime deps added to `[project]`.
2. **Lockfile** — `uv.lock` committed; CI and local dev run `uv sync --dev` (or `uv sync` with `[tool.uv] default-groups = ["dev"]`).
3. **Local one true path** — After clone: `uv sync --dev` → `uv run pytest -q` → `uv run pre-commit run --all-files` → `uv build`. CLI dev invocation: `uv run pgprovision …` (editable install from sync provides console script).
4. **CI ubuntu jobs** — Replace `actions/setup-python` + scattered `pip install` with `astral-sh/setup-uv@v5` (or current stable), `uv sync --dev`, and `uv run`/`uv build`. Remove `cache: 'pip'` where uv cache is enabled (`enable-cache: true` on setup-uv).
5. **Pre-commit CI** — Both `.github/workflows/ci.yml` `pre-commit` job and `.github/workflows/pre-commit.yml` use `uv sync --dev` + `uv run pre-commit run --all-files` (drop `pre-commit/action`).
6. **Build gate** — `uv build` + `uv run twine check dist/*` + install smoke on wheel and sdist.
7. **Publish gate** — `publish.needs` = `[pre-commit, unit, fedora-smoke, build]` only. Publish step uses `uv build`; upload `dist/*` unchanged.
8. **Fedora smoke** — New job `fedora-smoke` on `fedora:42` (or latest stable tag) container: dnf install git/python3/pip/sudo; `pip install .` with `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION`; same dry-run + importlib checks as current `rocky-smoke`.
9. **Ubuntu jobs** — `integration-ubuntu-smoke`, `user-mode-smoke` run only on `schedule` or `workflow_dispatch` (not on ordinary PR/push); **removed from `publish.needs`**.
10. **End-user docs** — `README.md` install section keeps `pip install pg-provision`; add **Contributing** section with uv commands.
11. **setuptools-scm pretend version** — Preserve `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION` env in container/smoke jobs that install from VCS without tags (`.github/workflows/ci.yml:L116`, `L189`, etc.).
12. **Fail fast** — CI steps use `set -euxo pipefail` in bash blocks; no silent `|| true` on install/build failures (existing uninstall smoke exception patterns unchanged).

## Implementation Steps

### Phase 1 — Project metadata and lockfile

**Goal:** Declare dev deps, generate a real lockfile, pin default Python for uv.

**Files to touch:**

- `pyproject.toml` — add `[dependency-groups]`, optional `[tool.uv]` with `default-groups = ["dev"]`
- `uv.lock` — regenerate and commit
- `.python-version` — new file, content `3.13`

**Commands:**

```bash
# After editing pyproject.toml
uv lock
uv sync --dev
uv run pytest -q --collect-only   # env resolves
uv run python -c "import pytest, build, twine, pre_commit; print('ok')"
```

**Exit criteria:**

- `[dependency-groups.dev]` lists pytest, build, twine, pre-commit.
- `uv.lock` tracked in git with resolved versions (not stub-only).
- `uv sync --dev` creates `.venv` and installs project editable.

**Depends on:** nothing.

---

### Phase 2 — Local developer experience and pre-commit hook

**Goal:** One documented local path; pytest hook uses project uv env.

**Files to touch:**

- `.pre-commit-config.yaml` — change local `pytest` hook to `language: system`, `entry: uv run pytest -q`, remove `additional_dependencies`
- `docs/pre-commit.md` — replace pip/pipx install with uv workflow
- `README.md` — add **Contributing** section (uv install link, sync, test, pre-commit, build); keep end-user `pip install` unchanged

**Commands (verification gate):**

```bash
uv sync --dev
uv run pytest -q
bash -n src/pgprovision/_sh/provision.sh src/pgprovision/_sh/os/*.sh
uv run pre-commit run --all-files
uv run pgprovision --dry-run
uv run pgprovision --user-mode --dry-run
```

**Exit criteria:**

- Pre-commit pytest hook runs via `uv run` (no isolated pytest-only env).
- README Contributing section documents the canonical commands.
- `docs/pre-commit.md` no longer recommends pip/pipx as the primary path.

**Depends on:** Phase 1.

---

### Phase 3 — CI core jobs (ubuntu-hosted, uv toolchain)

**Goal:** Migrate pre-commit, unit, build, and publish jobs to uv; enable uv caching.

**Files to touch:**

- `.github/workflows/ci.yml` — jobs: `pre-commit`, `unit`, `build`, `publish`
- `.github/workflows/pre-commit.yml` — standalone pre-commit workflow

**Proposed job patterns:**

**pre-commit** (both workflows):

```yaml
- uses: actions/checkout@v4
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
- run: uv sync --dev
- run: uv run pre-commit run --all-files
```

**unit** (matrix Python 3.9–3.13 — keep full matrix for package compatibility):

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    fetch-tags: true
- uses: astral-sh/setup-uv@v5
  with:
    python-version: ${{ matrix.python }}
    enable-cache: true
- run: uv sync --dev
- run: uv run pytest -q
- run: |
    uv run pgprovision --dry-run
    uv run pgprovision --user-mode --dry-run
    uv run pgprovision --uninstall-cluster --uninstall-only --dry-run \
      --data-dir "$PWD/.pgprovision-uninstall-smoke"
# keep existing importlib.resources artifact test block (python from uv venv)
```

**build:**

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    fetch-tags: true
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
- run: uv sync --dev
- run: uv build
- run: uv run twine check dist/*
- run: |
    uv pip install dist/*.whl
    pgprovision --help
    pgprovision --dry-run
    # ... existing dry-run variants
- run: uv pip uninstall pg-provision
- run: |
    uv pip install dist/*.tar.gz
    pgprovision --help
    # ... existing sdist smokes
```

**publish:**

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    fetch-tags: true
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
- run: uv sync --dev
- run: uv build
- uses: pypa/gh-action-pypi-publish@release/v1
  # dist/ from uv build
```

**Verification gate (local + push to branch):**

```bash
uv sync --dev
uv run pytest -q
uv build
uv run twine check dist/*
uv pip install dist/*.whl && pgprovision --dry-run
```

**Exit criteria:**

- No `python -m pip install` in pre-commit, unit, build, or publish jobs.
- No `actions/setup-python` + `cache: pip` in those jobs.
- PR CI green for pre-commit, unit, build on a test branch.

**Depends on:** Phase 1–2.

---

### Phase 4 — Platform smoke realignment and publish gates

**Goal:** Fedora-first gating; demote Ubuntu integration from publish path.

**Files to touch:**

- `.github/workflows/ci.yml` — replace `rocky-smoke` with `fedora-smoke`; adjust `if:` on Ubuntu jobs; update `publish.needs`
- `README.md` — CI matrix table (`README.md:L284-L297`)

**Changes:**

1. **Remove** job `rocky-smoke`.
2. **Add** job `fedora-smoke`:
   - `runs-on: ubuntu-latest`
   - `container: fedora:42` (pin; bump deliberately)
   - dnf install `git python3 python3-pip sudo`
   - checkout with `fetch-depth: 0`, `fetch-tags: true`
   - `pip install .` with `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION` (validates **end-user pip** on Fedora)
   - same dry-run + importlib smoke as rocky job
3. **`integration-ubuntu-smoke` and `user-mode-smoke`:** add `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'` (remove unconditional PR/push run).
4. **`publish.needs`:** change to `[pre-commit, unit, fedora-smoke, build]`.
5. **`integration-ubuntu-destructive`:** unchanged (already schedule/dispatch-only, not in publish.needs).

**Verification gate:**

```bash
# Local YAML review
grep -E 'fedora-smoke|rocky-smoke|publish:|needs:' .github/workflows/ci.yml

# After push
gh workflow run CI --ref "$(git branch --show-current)"   # if on default branch or via PR
gh run watch --exit-status
```

**Exit criteria:**

- `rocky-smoke` absent; `fedora-smoke` present and gating.
- `publish.needs` excludes Ubuntu smokes.
- Ubuntu smokes still runnable via dispatch/schedule.
- README CI table matches workflow.

**Depends on:** Phase 3.

---

### Phase 5 — Documentation sweep and acceptance

**Goal:** Remove hybrid `uv run python -m pip install -e .` guidance; align plans/prompts with uv path.

**Files to touch:**

- `docs/plans/phases-8-9-completion-plan.md` — live validation install lines (optional: minimal edit to gate commands only)
- `docs/plans/phases-8-9-uninstall-ci-plan.md` — same
- `docs/prompts/*-orchestrator.md` — replace `uv run python -m pip install -e .` with `uv sync --dev`
- Any new orchestrator prompts referencing pip for contributor setup

**Do not change:** end-user `pip install pg-provision` in README install section or test-plan install examples.

**Final verification gate (full):**

```bash
uv sync --dev
uv run pytest -q
bash -n src/pgprovision/_sh/provision.sh src/pgprovision/_sh/os/*.sh
uv run pre-commit run --all-files
uv build
uv run twine check dist/*
uv pip install dist/*.whl
pgprovision --dry-run
pgprovision --user-mode --dry-run
uv pip uninstall pg-provision
uv pip install dist/*.tar.gz
pgprovision --dry-run
```

**Exit criteria:**

- All acceptance criteria below checked.
- No contributor doc instructs `pip install -e .` or `uv run python -m pip install` as the primary setup path.

**Depends on:** Phase 4.

## Testing

| Requirement | Gate |
| --- | --- |
| R1 Dev deps declared | `uv sync --dev` succeeds; imports resolve |
| R2 Lockfile committed | `git ls-files uv.lock`; lock has >1 package |
| R3 Local one true path | Phase 2/5 command block |
| R4 CI uv toolchain | Workflow inspection; PR CI green |
| R5 Pre-commit CI via uv | Both workflow files use `uv run pre-commit` |
| R6 Build + twine | `uv build` + `uv run twine check dist/*` in CI |
| R7 Publish needs | Tag dry-run or workflow review: 4 jobs only |
| R8 Fedora smoke | `fedora-smoke` job green on PR |
| R9 Ubuntu demoted | PR push does not run ubuntu integration; dispatch works |
| R10 End-user pip docs | README install unchanged |
| R11 setuptools-scm pretend | Fedora smoke env var present |
| R12 Unit tests | `uv run pytest -q` — 177+ tests (current baseline) |
| R13 Shell syntax | `bash -n src/pgprovision/_sh/provision.sh src/pgprovision/_sh/os/*.sh` |
| R14 Wheel/sdist smoke | build job install + dry-run |
| R15 importlib artifacts | unit + fedora-smoke Python check blocks |

## CI migration matrix

| Current job | Proposed steps | Gating? | Platform |
| --- | --- | --- | --- |
| `pre-commit` | `setup-uv` → `uv sync --dev` → `uv run pre-commit run --all-files` | Yes | ubuntu-latest |
| `unit` | `setup-uv` (py3.9–3.13 matrix) → `uv sync --dev` → `uv run pytest -q` → `uv run pgprovision` smokes + importlib test | Yes | ubuntu-latest |
| `rocky-smoke` | **Remove** | — | — |
| `fedora-smoke` (**new**) | Fedora 42 container → dnf → `pip install .` (pretend version) → dry-run smokes + importlib test | Yes | Fedora container on ubuntu runner |
| `build` | `setup-uv` → `uv sync --dev` → `uv build` → `uv run twine check` → `uv pip install` wheel/sdist smokes | Yes | ubuntu-latest |
| `integration-ubuntu-smoke` | Unchanged steps; `if: schedule \|\| workflow_dispatch` | **No** | ubuntu-latest |
| `user-mode-smoke` | Unchanged steps; `if: schedule \|\| workflow_dispatch` | **No** | ubuntu-latest |
| `integration-ubuntu-destructive` | Unchanged; schedule/dispatch only | No | ubuntu-latest |
| `publish` | `setup-uv` → `uv sync --dev` → `uv build` → `gh-action-pypi-publish` | Yes (on tag) | ubuntu-latest |
| `.github/workflows/pre-commit.yml` | Same as CI `pre-commit` job | Informational (PR) | ubuntu-latest |

**Caching:** Use `enable-cache: true` on `astral-sh/setup-uv`. Remove `cache: 'pip'` from migrated jobs.

**Python version matrix:** Keep 3.9–3.13 on `unit` — runtime is shell-heavy but CLI/package must remain installable across declared classifiers (`pyproject.toml:L13-L19`). Default local/uv pin: 3.13 (`.python-version`).

## Rollout / rollback

**Rollout:**

1. Land Phase 1–2 on a feature branch; verify local gates.
2. Land Phase 3; open PR — ubuntu CI must go green before merge.
3. Land Phase 4; confirm `fedora-smoke` passes (container pull + dnf).
4. Land Phase 5 doc sweep.
5. First tag after merge validates publish path.

**Rollback:**

- Revert the merge commit(s). No database or runtime state — workflow-only change.
- If publish fails post-tag: yank is a PyPI operator action; workflow revert + retag is sufficient for tooling rollback.

**Transitional dual-path:** **Not recommended.** Migrate all ubuntu-hosted contributor jobs to uv in one Phase 3 PR. Exception: Fedora smoke intentionally uses **`pip install .`** to validate end-user install on RHEL-family — not a contributor dual-path.

## Acceptance criteria

- [ ] `[dependency-groups.dev]` in `pyproject.toml` with pytest, build, twine, pre-commit
- [ ] `uv.lock` committed with resolved dev dependency versions
- [ ] `.python-version` contains `3.13`
- [ ] README Contributing section documents uv workflow; end-user `pip install` unchanged
- [ ] `docs/pre-commit.md` updated for uv
- [ ] Local pytest pre-commit hook uses `uv run pytest -q`
- [ ] CI jobs `pre-commit`, `unit`, `build`, `publish` use `astral-sh/setup-uv` — no scattered `pip install` for dev tools
- [ ] `uv build` + `uv run twine check dist/*` in CI build job
- [ ] `fedora-smoke` replaces `rocky-smoke` and passes
- [ ] `publish.needs` = `[pre-commit, unit, fedora-smoke, build]`
- [ ] `integration-ubuntu-smoke` and `user-mode-smoke` not in `publish.needs`; run only on schedule/dispatch
- [ ] Orchestrator/plan gate commands use `uv sync --dev` / `uv run pytest` (no `uv run python -m pip install -e .`)
- [ ] Full local gate block (Phase 5) passes on Fedora 44 workstation
- [ ] Tag publish to PyPI succeeds with `uv build` artifacts

## Open questions

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Exact Fedora container tag: `fedora:42` vs `fedora:latest`? | Pin `fedora:42` (matches operator Fedora 44 family); bump explicitly when EOL. |
| 2 | Add optional `ubi9` smoke (non-gating)? | Defer; `fedora-smoke` + manual RHEL dispatch suffices for v1. |
| 3 | Upload `dist/` as CI artifact from `build` for `fedora-smoke` to test wheel instead of sdist install? | Optional hardening in follow-up; v1 keeps `pip install .` parity with rocky-smoke. |
| 4 | Prune sdist contents (`graphify-out/`, `docs/run/`)? | File separate packaging issue; not blocking uv migration. |

## Related follow-up (not this plan)

- **Fedora PGDG repo URL:** Fix `os_prepare_repos` in `src/pgprovision/_sh/os/rhel.sh:L235-L239` to detect Fedora vs RHEL (`rpm -E %fedora` / `pgdg-fedora-repo-latest.noarch.rpm`). Required before adding Fedora PGDG **integration** smoke to publish gates.
- **Sdist hygiene:** Tighten `MANIFEST.in` or setuptools-scm file selection so release tarballs exclude dev/graphify artifacts.

## Effort

| Phase | Estimate |
| --- | --- |
| 1 Lockfile + metadata | 0.5 day |
| 2 Local DX + pre-commit hook | 0.5 day |
| 3 CI core uv migration | 1 day |
| 4 Fedora smoke + publish.needs | 0.5 day |
| 5 Doc sweep + acceptance | 0.5 day |

**Total:** about 2–3 days.
