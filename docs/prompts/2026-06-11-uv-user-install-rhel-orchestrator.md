# Orchestrator — uv user install (RHEL/Fedora) (Phases 1–4)

**Date:** 2026-06-11 · **Role:** agentic implementation orchestrator (dispatches subagents) ·
**Authoritative plan:** `docs/plans/uv-user-install-rhel-plan.md` (READ IT FIRST AND IN FULL — it carries the
phase definitions, the per-item detail with `path:Lx-Ly` citations, and the success assertions; this prompt is the
operating doctrine around it).
**Worktree / branch:** `/home/tanarus/Repositories/pg-provision` (branch `main`, HEAD `dde6ef9`). **`uv sync --dev`
first on every fresh env; code gates use `uv run pytest -q`, `uv run pre-commit run --all-files`, and doc/CI
audits from the plan.**
**Key anchors:** user CLI `pgprovision` → `pyproject.toml:L28-L29`; shell entry `src/pgprovision/_sh/provision.sh`;
user backend `src/pgprovision/_sh/os/user.sh`; CI `.github/workflows/ci.yml` (`fedora-smoke:L82-L125`,
`build:L127-L173`, `user-mode-smoke:L211-L283` mirror for Phase 3, `publish:L348-L351`); operator docs
`README.md`, `docs/test-plan-rhel.md`; Fedora PGDG trap `src/pgprovision/_sh/os/rhel.sh:L235-L239`.

## Mission

Complete the packaging story from uv-migration Phases 1–5: **one operator install path** —
`uv tool install pg-provision` — with Fedora/RHEL-first docs and CI. Replace pip in publish-gating jobs
(`fedora-smoke`, `build`), add live `fedora-user-mode-smoke`, and remove `pip install pg-provision` from
operator-facing docs. Ubuntu CI jobs and `docs/test-plan-ubuntu.md` stay frozen (pip, schedule/dispatch only).

Work the plan in dependency order: **docs → publish-gating CI pip elimination → Fedora user-mode live gate →
reference sweep**. Within each phase: implement → code/doc gate green → smallest sufficient live run (where
applicable) → record → close. **Never** a big-bang patch followed by one validation at the end. The deliverable
is: every acceptance criterion in the plan checked with gate evidence, recorded in
`docs/run/uv-user-install-rhel/LEDGER.md`. Phase 5 (post-publish PyPI smoke) is **deferred** unless trivial.

This is **packaging/docs/CI work under live-container constraints**, not shell provisioning changes.
Minutes-long doc audits and local dry-runs; `gh run watch` on PR CI may run tens of minutes — delegate those to
background subagents.

---

## A. OPERATING DOCTRINE — context hygiene + delegation (read twice)

You are the **conductor**: hold the plan, the phase, the LEDGER/STATE, and the decisions. Push detail (long
logs, full tables, file-by-file diffs, multi-minute runs) **down into subagents and onto disk**. If you find
yourself pasting long command output into your own reasoning, stop and delegate.

1. **Never run a long step inline.** For anything expected to exceed ~5 min, **dispatch a subagent**
   (`run_in_background: true`) that launches it, monitors to completion, runs the phase's assertions, and
   returns a **compact** result (counts, pass/fail per assertion, anomalies, wall-clock — not raw logs). You
   consume the summary, not the firehose.
2. **Treat ~40% context utilization as a *quality* ceiling, not a capacity one.** Instruction-adherence and
   judgment degrade well before the window fills, so reserve the majority for incoming summaries and the
   reasoning to act on them. (The threshold scales with model capability — hand off earlier for a weaker model.)
3. **Don't babysit / poll background runs.** Launch, then do other useful work (do work *independent of the
   pending result* — refresh `STATE.md`, prepare the next phase's assertions, ground its anchors, write the
   LEDGER row; dispatch the next phase's implementation subagent **only if that phase doesn't depend on the
   gate now running** — its result can still fail — and never implement inline; the parent stays a conductor)
   and rely on the completion notification. Resume/await a subagent only when truly blocked on its result.
4. **One concern per subagent, tightly scoped.** Give each the exact commands, the exact assertions, and the
   exact return shape below. Subagents do **not** see this prompt or the operator's intent — spell everything
   out. **Mandatory return shape (≤ ~20 lines); full logs/tables/diffs go to disk, the return carries the
   *path*, never the contents:**

```
SUBAGENT RESULT
phase: <n>   scope: <one line>
status: ok | partial | failed | blocked
assertions:
  - <name>: pass|fail  (<observed vs expected>)
anomalies: <none | terse>
wall_clock: <hh:mm>
checkpoint: <label written | none>
artifacts: <path(s) to full log / tables / diff>
next: <single recommended action>
```

   A malformed, empty, or over-long return counts as `failed` — read the on-disk log via a fresh subagent;
   never infer success from a missing failure.
5. **Checkpoint expensive-to-reproduce state, not your context.** After each costly stage completes cleanly,
   capture what would be expensive to rebuild (a labeled git commit per phase boundary, green CI run URL,
   container smoke log) so a later phase or a successor restores instead of re-running upstream.
6. **Record to disk continuously** (see §F). The LEDGER is the durable memory; your context is scratch. Only
   one subagent mutates a given resource (CI workflow / docs / running container) at a time; read-only audits
   may overlap, but not against something a write-stage is currently producing.
7. **Hold a resumable snapshot, and hand off before you rot.** Maintain `STATE.md` (§F), overwritten at every
   phase boundary, as your single-read snapshot. When you approach the #2 ceiling — or at any phase boundary —
   refresh `STATE.md`, then compact or spawn a successor orchestrator. The successor's first act is to read
   `STATE.md` and **re-verify the cheap facts before trusting it** (HEAD sha, grep audits, checkpoints
   actually on disk, **and each `in_flight` subagent — a successor cannot await a background handle its
   predecessor launched, so confirm completion from each entry's `log_path`/sentinel on disk and treat any
   unfinished or unknown run as re-verify-or-re-dispatch, never as silently done**), then resume from
   `next_action`. Disk state goes stale; trust but re-verify. And when resuming into a phase that was interrupted
   mid-apply, confirm the change is **idempotent** (safe to re-apply) or reconcile its partial state before
   re-running — never blindly re-run a mutating step.

**Calibrate this doctrine to stage length.** PR CI watches may take tens of minutes — use background subagents
with notify-on-output for those. Doc edits and local dry-runs are minutes-long; keep `STATE.md` and structured
returns, but handoff pressure is lighter than multi-hour runs.

---

## B. Authoritative grounding (verified 2026-06-11 — trust but re-verify before acting)

- **Code state:** branch `main`, HEAD `dde6ef9`; prerequisite uv-migration Phases 1–5 landed (`uv.lock`,
  `[dependency-groups.dev]` at `pyproject.toml:L31-L37`, `.python-version` = `3.13`, contributor CI on
  `astral-sh/setup-uv@v5`).
- **End-user docs still pip:** `README.md:L7-L11` (`pip install pg-provision`); `README.md:L58-L60` (Contributing
  says pip remains user path); `docs/test-plan-rhel.md:L11-L16` (prerequisites pip).
- **User-mode docs exist in README:** `README.md:L29-L50` (bin-dir + tarball bootstrap); **NOT FOUND** in
  `docs/test-plan-rhel.md` (no user-mode section).
- **Publish-gating CI still uses pip/uv-pip:**
  - `fedora-smoke`: `python3 -m pip install .` (`ci.yml:L100-L109`); dnf installs `python3-pip` (`L103`).
  - `build`: `uv pip install dist/*` + `uv run --no-sync pgprovision` (`ci.yml:L145-L163`).
  - `publish.needs`: `[pre-commit, unit, fedora-smoke, build]` (`ci.yml:L351`).
- **Ubuntu jobs frozen (do not touch):** `integration-ubuntu-smoke:L175-L209`, `user-mode-smoke:L211-L283`,
  `integration-ubuntu-destructive:L285+` — all use `python -m pip install .`; schedule/dispatch only; do not
  gate publish.
- **Console script:** `pgprovision = "pgprovision.cli:main"` (`pyproject.toml:L28-L29`); zero runtime deps
  (`pyproject.toml:L5-L26` — no `[project.dependencies]`).
- **VCS install in CI:** `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION: 0.0.0.dev${{ github.run_number }}+g${{ github.sha }}`
  already used in `fedora-smoke` (`ci.yml:L105-L106`).
- **Fedora PGDG trap:** `rel="$(rpm -E %rhel)"` for PGDG RPM URL (`rhel.sh:L235-L239`); `%rhel` does not
  expand on Fedora — blocks `--repo pgdg` system provision; **does not block** user-mode with supplied binaries.
- **Local verify (plan fact):** `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION=0.0.0.dev1 uv tool install --force .`
  installs working `pgprovision --help` to `~/.local/bin/pgprovision`.
- **Ubuntu user-mode CI mirror:** `user-mode-smoke:L254-L283` — provision → stamp → destroy dry-run → confirmed
  destroy → uninstall dry-run; reuse flow for Fedora with dnf postgres packages instead of PGDG apt.

## C. Operator decisions

**LOCKED:**
1. **One user command:** `curl -LsSf https://astral.sh/uv/install.sh | sh` then `uv tool install pg-provision`;
   upgrades via `uv tool upgrade pg-provision`. Secondary: `uvx --from pg-provision pgprovision --dry-run`.
2. **Break change on docs:** remove all `pip install pg-provision` from README and RHEL guide; **no** compatibility
   shim text (“pip also works”).
3. **Development path unchanged:** clone → `uv sync --dev` → `uv run pytest` / `uv run pgprovision`.
4. **Ubuntu CI frozen:** do not modify `integration-ubuntu-*`, `user-mode-smoke`, or `docs/test-plan-ubuntu.md`.
5. **Fedora PGDG `%rhel` fix out of scope** — separate follow-up; `fedora-user-mode-smoke` uses dnf
   `postgresql-server postgresql`, not `--repo pgdg`.
6. **PostgreSQL major in user-mode smoke:** accept drift; derive `--pg-version` from `psql --version` in job
   setup (plan Open Q1).
7. **Tarball-bootstrap CI smoke:** defer (plan Open Q2); document manual path in RHEL guide only.
8. **README CI table:** keep Ubuntu rows as one-line “legacy schedule/dispatch” each; add
   `fedora-user-mode-smoke` row (plan Open Q3).
9. **Phase 5 post-publish PyPI smoke:** optional/deferred unless trivial (plan Open Q4).
10. **Publish gate sequencing:** add `fedora-user-mode-smoke` to `publish.needs` **only after** first green main
    run of that job — not in the same commit that introduces the job skeleton if untested.

**OPEN (confirm before sequencing; defaults in plan §Open questions):**
1. None — all four open questions resolved per locked defaults above.

**PRECEDENCE:** load-bearing corrections (§D) → these locked decisions → the plan body → this
template/reference. A blocker that collides with a locked decision is redesigned and recorded — never
silently weakened.

---

## D. Load-bearing corrections (read first, non-negotiable)

### HC-1 — `GITHUB_PATH` after `uv tool install` (silent `pgprovision: command not found`)
- **Trap:** `uv tool install` places `pgprovision` in `$HOME/.local/bin`, which is not on PATH in fresh CI steps;
  smoke steps fail with exit 127 while install succeeded.
- **REQUIRED:** every CI step that runs `pgprovision` after `uv tool install` must `echo "$HOME/.local/bin" >> "$GITHUB_PATH"` in the same or immediately prior step.
- **FORBIDDEN:** assuming checkout PATH includes tool bin; using `uv run --no-sync pgprovision` in publish-gating smokes (that validates contributor path, not user path).
- **Proved by:** Phase 2 live gate (`fedora-smoke`, `build` green on PR); Phase 3 live gate (`fedora-user-mode-smoke` green).

### HC-2 — `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION` for VCS installs
- **Trap:** container jobs installing from checkout without a valid PEP 440 pretend version fail setuptools-scm
  version resolution or produce invalid metadata.
- **REQUIRED:** VCS installs (`uv tool install --force .`) in Fedora jobs set
  `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION: 0.0.0.dev${{ github.run_number }}+g${{ github.sha }}`
  (existing pattern at `ci.yml:L105-L106`).
- **FORBIDDEN:** omitting pretend version on new Fedora container jobs; invalid/non-PEP-440 strings.
- **Proved by:** Phase 2 `fedora-smoke` install step succeeds; Phase 3 job install step succeeds.

### HC-3 — Fedora user-mode smoke must not use `--repo pgdg`
- **Trap:** copying Ubuntu PGDG system provision or RHEL `--repo pgdg` onto Fedora hits `%rhel` expansion bug
  (`rhel.sh:L235-L239`); job fails for unrelated packaging reason.
- **REQUIRED:** `fedora-user-mode-smoke` installs PostgreSQL via `dnf install postgresql-server postgresql`
  (Fedora repos); sets `--pg-bin-dir "$(dirname "$(command -v psql)")"`, `--repo none`, derives
  `--pg-version` from `psql --version`.
- **FORBIDDEN:** `pgprovision --repo pgdg` in the new job; relying on PGDG repo RPM on Fedora 42 container.
- **Proved by:** Phase 3 live gate (stamp file present, destroy round-trip, uninstall dry-run green).

### HC-4 — Publish gate update only after proven green main run
- **Trap:** adding `fedora-user-mode-smoke` to `publish.needs` in the same PR that introduces the job blocks
  all future tags if the job is flaky or misconfigured.
- **REQUIRED:** land job on main first; confirm green run; **then** 🛑 commit updating
  `publish.needs: [pre-commit, unit, fedora-smoke, build, fedora-user-mode-smoke]` (`ci.yml:L351`).
- **FORBIDDEN:** gating publish on a job that has never passed on main; weakening publish gates by removing
  existing jobs.
- **Proved by:** Phase 3 close when `gh run watch` shows green on main **and** `publish.needs` diff includes
  `fedora-user-mode-smoke`.

### HC-5 — No pip user path or compatibility shims in operator docs
- **Trap:** leaving “pip also works” or `pip install pg-provision` in README/RHEL guide contradicts the one-path
  story and acceptance criteria.
- **REQUIRED:** README Install + RHEL prerequisites use uv install script + `uv tool install pg-provision`;
  Contributing renamed **Development from source** without pip user-path language.
- **FORBIDDEN:** `pip install pg-provision` in `README.md` or `docs/test-plan-rhel.md`; “pip also works” hedging.
- **Proved by:** Phase 1 + Phase 4 code gates (`rg 'pip install pg-provision' README.md docs/test-plan-rhel.md` → zero matches).

### HC-6 — Do not mutate Ubuntu CI jobs or Ubuntu test plan
- **Trap:** drive-by “consistency” edits to `integration-ubuntu-smoke`, `user-mode-smoke`,
  `integration-ubuntu-destructive`, or `docs/test-plan-ubuntu.md` expand scope and churn unrelated pipelines.
- **REQUIRED:** leave Ubuntu job blocks and `docs/test-plan-ubuntu.md` unchanged; Phase 4 `rg` audit expects
  pip only inside Ubuntu job blocks in `ci.yml`.
- **FORBIDDEN:** converting Ubuntu jobs to uv in this orchestrator; deleting Ubuntu jobs from workflow.
- **Proved by:** Phase 4 audit (`rg 'pip install' .github/workflows/ci.yml | rg -v ubuntu` → zero outside Ubuntu blocks).

### HC-7 — `build` artifact smoke validates `uv tool install`, not `uv pip install`
- **Trap:** keeping `uv pip install dist/*` + `uv run --no-sync pgprovision` passes CI while user install path
  (`uv tool install --force dist/*`) is untested.
- **REQUIRED:** wheel and sdist smokes use `uv tool install --force dist/*.whl|*.tar.gz`, PATH update, direct
  `pgprovision` invocations; uninstall via `uv tool uninstall pg-provision` between wheel/sdist passes.
- **FORBIDDEN:** `uv pip install` / `uv run --no-sync pgprovision` in publish-gating build smokes after Phase 2.
- **Proved by:** Phase 2 `build` job green; grep `ci.yml` build steps for `uv pip install` → zero matches.

### HC-8 — `importlib.resources` artifact test must still pass after install-path change
- **Trap:** removing the Python inline test or pointing it at wrong interpreter after switching from pip to
  `uv tool install` hides packaged-shell regression.
- **REQUIRED:** retain artifact tests in `fedora-smoke` (`ci.yml:L116-L125`) and `build` (`ci.yml:L164-L173`);
  after `uv tool install`, run via `pgprovision`'s tool env python or `uv tool run pg-provision python - …`.
- **FORBIDDEN:** dropping artifact tests; using repo venv python that bypasses the installed tool env.
- **Proved by:** Phase 2 CI green including artifact test steps.

---

## E. Phase-by-phase dispatch (detail lives in plan §Implementation Steps / §Testing)

For each phase the plan gives Goal / Changes / Live verification / Assertions / Done-when / Risk. Drive it with
the doctrine above. What to dispatch:

| Phase | Implement (parent or impl-subagent) | Verify (subagent; assertions) | Close when |
|---|---|---|---|
| **1 Docs (README + RHEL guide)** | Replace Install with uv script + `uv tool install pg-provision` (`README.md:L7-L11`). Keep Quick start user-mode after Install (`README.md:L29-L50`). Rename Contributing → **Development from source**; remove pip user-path line (`README.md:L58-L60`). Update CI table stub for future `fedora-user-mode-smoke` (`README.md:L303-L316`). RHEL guide: prerequisites uv install (`docs/test-plan-rhel.md:L7-L16`); new **User-mode smoke** section (bin-dir + optional tarball subsection) mirroring README. Code gate: `grep -n 'pip install pg-provision' README.md docs/test-plan-rhel.md` → exit 1 if matches. | Local live gate: `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PG_PROVISION=0.0.0.dev1 uv tool install --force .`; `echo "$HOME/.local/bin" >> PATH` equivalent; `pgprovision --user-mode --dry-run`. Spot-check doc flag names against `provision.sh`. | HC-5 satisfied; local dry-run pass; doc grep clean. |
| **2 CI pip elimination (`fedora-smoke` + `build`)** | **`fedora-smoke`:** add `astral-sh/setup-uv@v5`; replace pip install with `uv tool install --force .` + `GITHUB_PATH`; drop `python3-pip` from dnf (`ci.yml:L100-L109`); keep importlib test (HC-8). **`build`:** replace `uv pip install` blocks with `uv tool install --force dist/*` + PATH + direct `pgprovision` smokes + `uv tool uninstall pg-provision` between wheel/sdist (`ci.yml:L145-L163`). Remove stale `PIP_*` env from fedora-smoke if unused. | Push branch; background subagent `gh run watch --exit-status` for `fedora-smoke` + `build`. Assert job logs show `uv tool install`, not `pip install` or `uv pip install`. | HC-1, HC-2, HC-7, HC-8 satisfied; both jobs green on PR. |
| **3 `fedora-user-mode-smoke` + publish gate** 🛑 | New job: `ubuntu-latest` + `container: fedora:42`; trigger `push`/`pull_request` to main (same as other publish gates; **not** schedule-only). Flow: checkout (full clone) → setup-uv → pretend version → `uv tool install --force .` + PATH → `dnf install postgresql-server postgresql git sudo` → derive `PG_MAJOR` from `psql --version` → mirror `user-mode-smoke:L254-L283` with Fedora paths (`PG_BIN_DIR="$(dirname "$(command -v psql)")"`). **Do not** add to `publish.needs` until first green **main** run (HC-4). | PR CI: job green (`stamp file`, destroy dry-run + confirmed destroy, uninstall dry-run). After merge: watch main run green → 🛑 operator pause → commit `publish.needs` includes `fedora-user-mode-smoke`. | HC-3 + HC-4 satisfied; job green on main; publish gate updated. |
| **4 Reference sweep** | Final README CI table sync (`fedora-user-mode-smoke` row, Ubuntu legacy lines). Verify `docs/pre-commit.md` has no pip primary path. Optional: stale operator pip refs in old orchestrator prompts (low priority). | Code gate: `rg 'pip install pg-provision' README.md docs/test-plan-rhel.md docs/pre-commit.md` → zero. `rg 'pip install' .github/workflows/ci.yml | rg -v ubuntu` → zero outside Ubuntu blocks. Full local gate from plan acceptance: `uv sync --dev && uv run pytest -q && uv run pre-commit run --all-files && uv tool install --force . && pgprovision --user-mode --dry-run`. | Phase 4 rg audits clean; acceptance checklist complete. |
| **5 Post-publish PyPI smoke (deferred)** | Only if trivial: after tag publish, `uv tool install pg-provision==${TAG#v}` + dry-runs. | Post-tag live gate. | Record in LEDGER as `deferred` or `closed` with evidence. |

**Reusable audit script** — write once to `docs/run/uv-user-install-rhel/assert/no-pip-user-path.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
rg 'pip install pg-provision' README.md docs/test-plan-rhel.md docs/pre-commit.md && exit 1
rg 'pip install' .github/workflows/ci.yml | rg -v ubuntu && exit 1
echo "ok: no pip user path in RHEL/Fedora operator surfaces"
```

Every verify-subagent writes full output to `docs/run/uv-user-install-rhel/logs/phase-<n>-<slug>.log`.

**Code gate commands (phases touching CI or when validating locally):**

```bash
uv sync --dev
uv run pytest -q
uv run pre-commit run --all-files
bash docs/run/uv-user-install-rhel/assert/no-pip-user-path.sh
```

---

## F. Traceability: LEDGER + STATE.md (maintain continuously)

Two on-disk records under `docs/run/uv-user-install-rhel/`. **Disk is the durable memory; your context is scratch.**

- **`LEDGER.md` — append-only narrative.** One row per phase (plus a sub-row per deliverable): `phase |
  deliverable | code_status (todo/patched/code-green) | live_status (pending/pass/fail) | evidence (command,
  output snippet, path) | notes`. The audit trail; not resumable in one read.
- **`STATE.md` — single-read continuation snapshot, overwritten at every phase boundary.** System of record
  for handoff/resume:

```
# uv user install (RHEL/Fedora) — orchestrator STATE  (overwrite each phase boundary)
phase: <n>   status: in-progress | awaiting-subagent | blocked
items:   closed:[...]  open:[...]  deferred:[5-post-publish-pypi]
code:    HEAD <sha>  env_built: y/n  pytest: green/red  pre-commit: green/red
ci:      pr_url: <url|n/a>  fedora-smoke: <pending|green|red>  build: <pending|green|red>
         fedora-user-mode-smoke: <pending|green|red|not-yet-on-main>  publish_needs_updated: y/n
decisions_open: [<ids> | resolved: pg-major=drift, tarball-ci=defer, phase5=defer]
in_flight: [ {subagent, phase, scope, sentinel?, log_path}, ... ]
next_action: <single concrete step>
```

- **`FINAL_REPORT.md`** — per-phase outcomes + plan acceptance criteria, with live evidence paths.

Done only when every LEDGER row is `code-green` + (where applicable) `live-pass`. Phase 5 may remain
`deferred` without blocking done.

---

## G. Hard constraints (apply to every slice)

- **Scope:** packaging, docs, and CI only — no changes to `provision.sh`, backends, or shell provisioning logic
  unless a live gate reveals a bug (then fix minimally and record).
- **Ubuntu frozen:** do not edit Ubuntu CI jobs or `docs/test-plan-ubuntu.md` (HC-6).
- **Fedora PGDG fix out of scope:** do not patch `rhel.sh:L235-L239` in this run.
- **Back-out / rollback:** revert workflow/doc commits; PyPI artifacts unchanged; no runtime state migration
  (plan §Rollout).
- **Fail fast with actionable diagnostics.** CI steps use `set -euxo pipefail`; failures name job, step, and
  next action.
- **No backwards-compat shims, aliases, or silent fallbacks.** Docs state one user install path; refactors
  update all touched operator surfaces or fail the audit gate.
- **Config discipline:** no new `os.environ`/`os.getenv` in Python application code; CI env vars only in
  workflow YAML.
- **Docstrings:** any function/method/class added or changed gets a current, accurate docstring (unlikely in
  this docs/CI-only run).
- **Don't use the word "preflight"** — use check / validate / verify.
- **Graphify:** after modifying code under `src/` (unlikely), run `graphify update .` once before handoff.
- **Commit discipline:** one logical slice per commit; do not commit unless operator asks.

---

## H. Success criteria

- README Install uses `uv tool install pg-provision`; no pip user path; user-mode quick start follows uv install.
- `docs/test-plan-rhel.md` prerequisites and new user-mode section use uv; tarball bootstrap documented for manual runs.
- `fedora-smoke` uses `uv tool install`; no pip in job.
- `build` wheel/sdist smokes use `uv tool install --force dist/*`; no `uv pip install` in build smokes.
- `fedora-user-mode-smoke` exists, passes on main, and gates publish (`publish.needs` includes it).
- No `pip install pg-provision` in README or RHEL guide; Ubuntu CI and test plan untouched.
- Local acceptance gate passes:
  ```bash
  uv sync --dev && uv run pytest -q && uv run pre-commit run --all-files
  uv tool install --force . && pgprovision --user-mode --dry-run
  ```
- **Context hygiene:** CI watches delegated to subagents; `STATE.md` + `LEDGER.md` current on disk.

---

## I. If you get blocked

Stop and report with diagnostics (operation, identifiers, what you observed, the most likely next step) — do
not improvise repeated attempts or fabricate progress. Genuine blockers:

- **`fedora-user-mode-smoke` fails on PostgreSQL major mismatch** — capture `psql --version` and dnf package
  list from job log; adjust `--pg-version` derivation; do not switch to `--repo pgdg` (HC-3).
- **`uv tool install dist/*.whl` fails on build job** — verify wheel name/glob, pretend version not needed for
  dist install; check whether `uv tool uninstall pg-provision` is required between wheel and sdist passes.
- **importlib.resources test fails after install-path change** — identify which Python interpreter runs the test;
  use tool-env python (`uv tool run pg-provision python -c '…'`) per HC-8.
- **Publish gate chicken-and-egg** — if job must be on main to prove green but PR needs green to merge: land job
  without `publish.needs` first (HC-4), merge, then follow-up commit for gate update.
- **Operator refuses doc break change** — surface conflict with locked decision #2; do not reintroduce pip shims.

Surface the decision; don't silently change scope.
