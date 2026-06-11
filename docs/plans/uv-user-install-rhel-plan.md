# uv User Install Plan (RHEL/Fedora)

## Purpose

Complete the packaging story started in [uv-migration-plan.md](uv-migration-plan.md): **one install path for everyone** — `uv tool install pg-provision` — including operators running **user-mode PostgreSQL** (no sudo, home-directory PGDATA, optional tarball bootstrap). Align docs and CI with **Fedora/RHEL-family** priority; do **not** expand or migrate Ubuntu coverage in this plan.

**Prerequisite:** uv-migration-plan Phases 1–5 are landed (`uv.lock`, `[dependency-groups.dev]`, `.python-version`, ubuntu-hosted contributor CI on uv, `fedora-smoke` dry-run container, publish gates = `pre-commit` + `unit` + `fedora-smoke` + `build`).

## Facts

### Post–v1 baseline (verified 2026-06-11)

1. **Contributor CI is on uv** — **FACT:** `pre-commit`, `unit`, `build`, and `publish` jobs use `astral-sh/setup-uv@v5`, `uv sync --dev`, `uv run`, and `uv build` (`.github/workflows/ci.yml:L20-L30`, `L45-L51`, `L136-L144`, `L363-L371`).

2. **Lockfile and dev deps exist** — **FACT:** `uv.lock` is tracked (~1300 lines); `[dependency-groups.dev]` lists pytest, build, twine, pre-commit (`pyproject.toml:L31-L37`); `.python-version` pins `3.13`.

3. **End-user docs still say pip** — **FACT:** README Install section: `pip install pg-provision` (`README.md:L7-L11`); Contributing says uv is contributor-only and pip remains the user path (`README.md:L58-L60`); RHEL test guide prerequisites use pip (`docs/test-plan-rhel.md:L11-L16`).

4. **Remaining pip in CI** — **FACT:**

   | Job | Install pattern | Citations |
   | --- | --- | --- |
   | `fedora-smoke` | `python3 -m pip install .` in Fedora 42 container | `.github/workflows/ci.yml:L100-L109` |
   | `build` (artifact smoke) | `uv pip install dist/*` then `uv run --no-sync pgprovision` | `.github/workflows/ci.yml:L145-L163` |
   | `integration-ubuntu-smoke` | `python -m pip install .` | `.github/workflows/ci.yml:L192-L195` |
   | `user-mode-smoke` | `python -m pip install .` | `.github/workflows/ci.yml:L228-L231` |
   | `integration-ubuntu-destructive` | `python -m pip install .` | `.github/workflows/ci.yml:L306-L309` |

5. **Publish gates are RHEL/Fedora-first already** — **FACT:** `publish.needs: [pre-commit, unit, fedora-smoke, build]` (`.github/workflows/ci.yml:L351`); Ubuntu integration jobs are schedule/dispatch only and do not gate publish (`README.md:L311-L316`).

6. **User-mode is documented in README but not RHEL guide** — **FACT:** README Quick start covers `--user-mode` and tarball bootstrap (`README.md:L29-L50`); `docs/test-plan-rhel.md` has **no** user-mode scenarios (grep: no matches).

7. **Fedora PGDG repo URL bug** — **FACT:** RHEL backend uses `rel="$(rpm -E %rhel)"` for PGDG RPM URL (`src/pgprovision/_sh/os/rhel.sh:L235-L239`). On Fedora, `%rhel` does not expand; `--repo pgdg` system-mode provision fails on Fedora until fixed. **Does not block** dry-run smoke or user-mode provision when PostgreSQL binaries are supplied via `--pg-bin-dir` or tarball bootstrap.

8. **`uv tool install` works for this package** — **FACT (local verify):** `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION=0.0.0.dev1 uv tool install --force .` installs `pgprovision` to `~/.local/bin/pgprovision` with working `--help`. PyPI path: `uv tool install pg-provision` (same console script entrypoint: `pyproject.toml:L28-L29`).

9. **Zero runtime Python dependencies** — **FACT:** No `[project.dependencies]` (`pyproject.toml:L5-L26`); uv tool env is self-contained.

10. **Pre-commit hook uses uv** — **FACT:** Local pytest hook is `language: system`, `entry: uv run pytest -q` (`.pre-commit-config.yaml:L80-L81`); `docs/pre-commit.md` documents uv sync path.

### NOT FOUND (this plan may add)

- RHEL/Fedora user-mode live validation section in `docs/test-plan-rhel.md`
- CI job that installs via `uv tool install` and runs user-mode provision on Fedora/RHEL
- Post-publish smoke installing from PyPI via `uv tool install pg-provision`

## Inferences

- **`uv tool install pg-provision`** is the correct user-facing command (pipx replacement): isolated tool env, `pgprovision` on PATH, no venv management for operators.
- **`uv sync --dev`** remains the repo-hack path only; docs should not imply two different *products*, just two contexts (installed tool vs cloned source).
- **`build` job should smoke via `uv tool install --force dist/*`**, not `uv pip install`, so CI validates the same path documented for users.
- **`fedora-smoke` should install via `uv tool install --force .`**, replacing the last publish-gating pip usage.
- **User-mode integration belongs on Fedora**, not Ubuntu: add `fedora-user-mode-smoke` using distro PostgreSQL binaries (dnf) + `uv tool install`; avoids PGDG repo bug for system package install while proving the user-mode path operators care about.
- **Ubuntu CI jobs can stay frozen** (still pip, still schedule/dispatch); this plan does not touch them. README CI table should reflect Fedora/RHEL as primary gates and de-emphasize Ubuntu rows.
- **RHEL test guide needs a user-mode section** with the same uv install prerequisite and copy/paste flows from README (bootstrap tarball variant included).

## Scope

### In scope

| Item | Detail |
| --- | --- |
| Canonical user install | Document `uv tool install pg-provision` everywhere operators look (README, RHEL guide) |
| Remove pip as documented install path | No `pip install pg-provision` in user-facing docs touched by this plan |
| `fedora-smoke` | Replace pip with `setup-uv` + `uv tool install --force .` |
| `build` artifact smoke | Replace `uv pip install` with `uv tool install --force dist/*` |
| New `fedora-user-mode-smoke` | Schedule/dispatch job: uv tool install + user-mode provision/stamp/destroy/uninstall dry-run on Fedora 42 |
| RHEL test guide | Prerequisites → uv; add user-mode validation section |
| README restructure | Install → uv tool install; user-mode promoted; Contributing → “Development from source” |
| Publish gate update | Add `fedora-user-mode-smoke` to `publish.needs` once green (operator priority) |

### Out of scope

| Item | Reason |
| --- | --- |
| Ubuntu CI job migration | Operator priority is RHEL/Fedora; leave `integration-ubuntu-*` and `user-mode-smoke` (Ubuntu) unchanged |
| `docs/test-plan-ubuntu.md` updates | Ubuntu guide not maintained in this plan |
| Build backend / PyPI publishing mechanism change | Still `uv build` + OIDC trusted publishing |
| Shell provisioning logic changes | Packaging/docs/CI only |
| Fedora PGDG `%rhel` fix | Separate follow-up; blocks `--repo pgdg` system provision on Fedora, not user-mode with supplied binaries |
| Self-hosted RHEL runner provisioning | Manual dispatch remains documented |
| Removing Ubuntu jobs from workflow | Frozen, not deleted — avoids unrelated CI churn |
| Sdist content pruning | Pre-existing packaging hygiene task |

## Requirements

1. **One user command** — Operators install with:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv tool install pg-provision
   ```
   Upgrades: `uv tool upgrade pg-provision`. Optional try-without-install: `uvx --from pg-provision pgprovision --dry-run` (documented secondary, not primary).

2. **User-mode is first-class in RHEL docs** — `docs/test-plan-rhel.md` gains prerequisites (uv) and a user-mode section mirroring README flows (bin-dir and tarball bootstrap variants).

3. **No pip in publish-gating CI** — `fedora-smoke` and `build` artifact smokes use `uv tool install`.

4. **Fedora user-mode gate** — New `fedora-user-mode-smoke` job proves: uv tool install → user-mode provision → stamp file → logical destroy dry-run + confirmed destroy → uninstall dry-run. Uses Fedora container PostgreSQL server packages for binaries (not pg-provision `--repo pgdg`).

5. **Break change on docs** — Remove all `pip install pg-provision` from README and RHEL guide; no compatibility shim text (“pip also works”).

6. **Development path unchanged** — Clone → `uv sync --dev` → `uv run pytest` / `uv run pgprovision`.

7. **setuptools-scm pretend version** — Container jobs installing from VCS keep `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION` with a valid PEP 440 string (e.g. `0.0.0.dev${{ github.run_number }}+g${{ github.sha }}`).

8. **PATH** — CI steps using `uv tool install` must append `$HOME/.local/bin` to `GITHUB_PATH` before invoking `pgprovision`.

## Implementation Steps

### Phase 1 — README and RHEL guide (docs)

**Goal:** Operators see one install story; user-mode is the headline use case on RHEL/Fedora.

**Files:**

- `README.md`
- `docs/test-plan-rhel.md`

**README changes:**

1. Replace Install block with uv install + `uv tool install pg-provision`.
2. Keep Quick start user-mode examples immediately after Install (already present; ensure they follow uv install).
3. Rename **Contributing** → **Development from source**; remove “end-user install path remains pip”.
4. Update **CI and release gates** table: add `fedora-user-mode-smoke`; note Ubuntu jobs as legacy/schedule-only (one line each, not primary).

**RHEL guide changes:**

1. Prerequisites §0: uv install + `uv tool install pg-provision` instead of pip.
2. New section (e.g. **User-mode smoke**, after dry-run or before cleanup): home-directory PGDATA, `--pg-bin-dir` from installed PostgreSQL packages, provision/stamp/destroy/uninstall dry-run commands aligned with README env knobs.
3. Optional subsection: tarball bootstrap (`--bootstrap-tarball`, SHA256 required) for environments without preinstalled server packages.

**Verification gate (local, no infra):**

```bash
# doc review only — spot-check examples match flag names in provision.sh
grep -n 'pip install pg-provision' README.md docs/test-plan-rhel.md && exit 1 || true
uv tool install --force .  # with pretend version if needed
pgprovision --user-mode --dry-run
```

**Depends on:** nothing.

---

### Phase 2 — CI: `fedora-smoke` and `build` on `uv tool install`

**Goal:** Eliminate pip from publish-gating jobs; CI mirrors user install path.

**Files:**

- `.github/workflows/ci.yml` — jobs `fedora-smoke`, `build`

**`fedora-smoke` pattern:**

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    fetch-tags: true
- uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
- name: Install package via uv tool
  env:
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION: 0.0.0.dev${{ github.run_number }}+g${{ github.sha }}
  run: |
    set -euxo pipefail
    uv tool install --force .
    echo "$HOME/.local/bin" >> "$GITHUB_PATH"
- name: "Smoke: pgprovision dry-runs"
  run: |
    set -euxo pipefail
    pgprovision --dry-run
    pgprovision --user-mode --dry-run
    pgprovision --uninstall-cluster --uninstall-only --dry-run \
      --data-dir "$PWD/.pgprovision-uninstall-smoke"
# keep importlib.resources artifact test (use pgprovision's python or uv tool run)
```

Remove `python3-pip` from dnf install step; keep `git`, `python3`, `sudo` as needed.

**`build` job — replace `uv pip install` blocks:**

```yaml
- name: Install wheel and smoke
  run: |
    set -euxo pipefail
    uv tool install --force dist/*.whl
    echo "$HOME/.local/bin" >> "$GITHUB_PATH"
    pgprovision --help
    pgprovision --dry-run
    pgprovision --user-mode --dry-run
    pgprovision --uninstall-cluster --uninstall-only --dry-run \
      --data-dir "$PWD/.pgprovision-uninstall-smoke"
- name: Uninstall wheel tool
  run: uv tool uninstall pg-provision
- name: Install sdist and smoke
  run: |
    set -euxo pipefail
    uv tool install --force dist/*.tar.gz
    echo "$HOME/.local/bin" >> "$GITHUB_PATH"
    pgprovision --help
    # ... same smokes
```

**Verification gate:** PR CI green for `fedora-smoke` and `build`.

**Depends on:** Phase 1 (docs can land in same PR or precede).

---

### Phase 3 — `fedora-user-mode-smoke` job

**Goal:** Live user-mode integration on Fedora; replaces Ubuntu user-mode as the operator-relevant gate.

**Files:**

- `.github/workflows/ci.yml` — new job + `publish.needs` update

**Job sketch:**

| Property | Value |
| --- | --- |
| Name | `fedora-user-mode-smoke` |
| Trigger | `push`/`pull_request` to main (same as other publish gates) |
| Runner | `ubuntu-latest` + `container: fedora:42` |
| CLI install | `uv tool install --force .` + `GITHUB_PATH` |
| PostgreSQL binaries | `dnf install postgresql-server postgresql` (Fedora repos; record resolved major in job env) |
| Flow | user-mode provision → assert stamp → destroy dry-run → confirmed destroy → uninstall dry-run |

**Example core step:**

```bash
PGPROVISION_BIN="$(command -v pgprovision)"
PG_BIN_DIR="$(dirname "$(command -v psql)")"
BASE="$PWD/.pgprovision-ci-user"
SOCKET_GROUP="$(id -gn)"
"$PGPROVISION_BIN" --user-mode --pg-version "$PG_MAJOR" \
  --pg-bin-dir "$PG_BIN_DIR" \
  --user-base-dir "$BASE" --data-dir "$BASE/data" \
  --port 55432 --repo none --unix-socket-group "$SOCKET_GROUP" \
  --create-db pgprov_user_ci
test -f "$BASE/data/.pgprovision_provisioned.json"
# ... destroy + uninstall dry-run (mirror ubuntu user-mode-smoke logic)
```

**Publish gate:** After job is green on main, set `publish.needs: [pre-commit, unit, fedora-smoke, build, fedora-user-mode-smoke]`.

**Verification gate:** PR with job enabled; `gh run watch` until green.

**Depends on:** Phase 2 (same workflow file conventions).

**Risk:** Fedora repo PostgreSQL major may drift; pin discovery via `psql --version` and pass matching `--pg-version`. Document in job comment.

---

### Phase 4 — Doc sweep and stale references

**Goal:** No user-facing pip install instructions remain in RHEL/Fedora operator paths.

**Files:**

- `README.md` — final CI table sync
- `docs/test-plan-rhel.md`
- `docs/pre-commit.md` — already uv; verify no pipx primary path
- Orchestrator prompts that say `pip install -e .` for **operator** setup (optional cleanup; low priority)

**Do not touch:**

- `docs/test-plan-ubuntu.md`
- Ubuntu CI jobs in `.github/workflows/ci.yml`

**Verification gate:**

```bash
rg 'pip install pg-provision' README.md docs/test-plan-rhel.md docs/pre-commit.md
# expect zero matches
rg 'pip install' .github/workflows/ci.yml | rg -v ubuntu
# expect zero matches outside ubuntu job blocks
```

**Depends on:** Phases 1–3.

---

### Phase 5 — Optional post-publish PyPI smoke

**Goal:** Prove released artifacts install via documented user path.

**Trigger:** Tag publish workflow or follow-up job after `gh-action-pypi-publish`.

**Step:**

```bash
uv tool install pg-provision==${TAG#v}
pgprovision --dry-run
pgprovision --user-mode --dry-run
```

**Out of scope for initial merge** unless trivial to add; list as follow-up.

**Depends on:** Phases 1–2.

## CI matrix (target state)

| Job | Install | Platform | Gates publish? |
| --- | --- | --- | --- |
| `pre-commit` | `uv sync --dev` | ubuntu-latest | Yes |
| `unit` | `uv sync --dev` | ubuntu-latest, py 3.9–3.13 | Yes |
| `fedora-smoke` | **`uv tool install --force .`** | Fedora 42 container | Yes |
| `build` | `uv build` → **`uv tool install --force dist/*`** | ubuntu-latest | Yes |
| **`fedora-user-mode-smoke`** (**new**) | **`uv tool install --force .`** + dnf postgres | Fedora 42 container | **Yes** |
| `integration-ubuntu-smoke` | pip (unchanged) | ubuntu-latest | No |
| `user-mode-smoke` (Ubuntu) | pip (unchanged) | ubuntu-latest | No |
| `integration-ubuntu-destructive` | pip (unchanged) | ubuntu-latest | No |
| `publish` | `uv build` | ubuntu-latest | tags only |

## Testing

| Phase | Code/doc gate | Live gate |
| --- | --- | --- |
| 1 | No `pip install pg-provision` in README/RHEL guide | Local `uv tool install --force .` + `--user-mode --dry-run` |
| 2 | PR CI: `fedora-smoke`, `build` green | — |
| 3 | PR CI: `fedora-user-mode-smoke` green | Stamp file + destroy round-trip in container |
| 4 | `rg` audit clean for RHEL/Fedora docs | — |
| 5 | Post-tag `uv tool install pg-provision` from PyPI | `--dry-run` |

## Rollout

1. Land Phase 1 (docs) — can ship independently.
2. Land Phase 2 — unblocks pip-free publish gates.
3. Land Phase 3 — add publish gate only after first green main run.
4. Phase 4 sweep in same PR as 2+3 or immediately after.
5. Phase 5 when convenient.

**Rollback:** Revert workflow/doc commits. PyPI artifacts unchanged. No runtime state migration.

## Acceptance criteria

- [ ] README Install uses `uv tool install pg-provision`; no pip user path
- [ ] README user-mode quick start follows uv install
- [ ] `docs/test-plan-rhel.md` prerequisites and user-mode section use uv
- [ ] `fedora-smoke` uses `uv tool install`; no pip in job
- [ ] `build` wheel/sdist smokes use `uv tool install --force dist/*`
- [ ] `fedora-user-mode-smoke` exists and gates publish
- [ ] `publish.needs` includes `fedora-user-mode-smoke`
- [ ] No `pip install pg-provision` in README or RHEL guide
- [ ] Ubuntu CI jobs untouched; Ubuntu test plan untouched
- [ ] Local gate passes on Fedora/RHEL workstation:
  ```bash
  uv sync --dev
  uv run pytest -q
  uv run pre-commit run --all-files
  uv tool install --force .
  pgprovision --user-mode --dry-run
  ```

## Open questions

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Pin Fedora PostgreSQL major in user-mode smoke via dnf versionlock or accept drift? | Accept drift; derive `--pg-version` from `psql --version` in job setup |
| 2 | Add tarball-bootstrap smoke in CI? | Defer; heavier; document in RHEL guide for manual runs |
| 3 | Remove Ubuntu rows from README CI table entirely? | Keep one line “legacy schedule/dispatch” each; don’t delete job names |
| 4 | Post-publish PyPI `uv tool install` smoke in same workflow? | Phase 5 optional; avoids race with PyPI index propagation |

## Related follow-ups (not this plan)

- **Fedora PGDG `%rhel` fix** (`src/pgprovision/_sh/os/rhel.sh:L235-L239`) — enables `--repo pgdg` system provision on Fedora; prerequisite for Fedora PGDG *system-mode* integration smoke
- **Self-hosted RHEL integration** — manual runner per README; install via `uv tool install pg-provision`
- **Sdist hygiene** — exclude `graphify-out/`, `docs/run/` from release tarball
- **Retire Ubuntu CI** — separate decision when operator no longer needs upstream compatibility signal

## Effort

| Phase | Estimate |
| --- | --- |
| 1 Docs (README + RHEL guide) | 0.5 day |
| 2 CI pip elimination (fedora-smoke + build) | 0.5 day |
| 3 fedora-user-mode-smoke | 0.5–1 day |
| 4 Reference sweep | 0.25 day |
| 5 Post-publish PyPI smoke (optional) | 0.25 day |

**Total:** about 1.5–2.5 days.
