# Planning prompt: migrate pg-provision development and CI to uv

Use this prompt with a coding agent or LLM to **analyze the repository's current Python packaging and workflow**, then **author a single implementation plan** for migrating contributor workflows and CI to **uv**, while keeping the **end-user PyPI install story** (`pip install pg-provision`) unchanged.

**Do not implement code.** Your only artifact is the plan document saved to `docs/plans/`.

---

## Your role

You are planning a **workflow migration** for **pg-provision** — an idempotent PostgreSQL provisioner (`pgprovision` CLI) wrapping portable Bash scripts. You will:

1. **Investigate** the repository and reconcile prior assumptions against current code and CI (function/line granularity, citations required).
2. **Write** one implementation plan in execution order, with per-phase tasks, verification gates, exit criteria, and dependencies.
3. **Save** the plan to:

   ```
   docs/plans/uv-migration-plan.md
   ```

   Create `docs/plans/` if it does not exist. Do not save under `docs/prompts/`.

**Prerequisite reading (in-repo):**

| Document | Path |
|----------|------|
| This planning prompt | `docs/prompts/2026-06-11-plan-uv-migration.md` |
| Package metadata & pytest config | `pyproject.toml` |
| CI workflow | `.github/workflows/ci.yml` |
| Pre-commit workflow | `.github/workflows/pre-commit.yml` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| Contributor README | `README.md` |
| Example completed plan (structure reference) | `docs/plans/phases-8-9-completion-plan.md` |

If prior chat context claims facts about uv usage, **verify every claim in the repo** before writing the plan.

---

## Operator context (verified 2026-06-11 — re-verify before acting)

The operator uses **uv** for almost everything and wants this project aligned with that workflow.

**Platform priority (explicit):**

- **In scope for validation and CI design:** Fedora and RHEL (RHEL-family: RHEL, Rocky, Alma, Fedora).
- **Out of scope for this migration:** Ubuntu integration jobs, Rocky-specific smoke as a primary gate, and disposable Ubuntu live validation. Do not spend plan phases on Ubuntu-centric CI unless needed to avoid regressions during transition.

**Known local state (re-verify):**

- `uv` is available on the operator's Fedora 44 workstation.
- Local gates already use `uv run pytest -q` and `uv run pre-commit run --all-files` in recent run artifacts under `docs/run/`.
- `uv.lock` may exist locally but is **not necessarily committed**; inspect `git status` and `git ls-files uv.lock`.
- CI (`.github/workflows/ci.yml`) still uses `actions/setup-python` + `python -m pip install …` across jobs.
- The package has **zero runtime Python dependencies**; dev deps (pytest, build, twine, pre-commit) are installed ad hoc today.
- Build backend is **setuptools + setuptools-scm**; PyPI publish uses `python -m build` and `pypa/gh-action-pypi-publish`.
- End users install via `pip install pg-provision` from PyPI — **this must remain supported and documented**.

**Separate concern (mention but do not solve in this plan unless blocking uv migration):**

- Fedora PGDG repo setup in `src/pgprovision/_sh/os/rhel.sh` uses `rpm -E %rhel`, which does not expand on Fedora (`%rhel` stays literal). PGDG on Fedora uses `F-<version>-<arch>` and `pgdg-fedora-repo-latest.noarch.rpm`. Flag this as a **related follow-up**, not part of the uv migration, unless the operator's Fedora host is the primary live-validation target for CI changes.

---

## Repository layout (starting points)

| Area | Path |
|------|------|
| CLI entry | `src/pgprovision/cli.py` |
| Main orchestrator | `src/pgprovision/_sh/provision.sh` |
| OS backends | `src/pgprovision/_sh/os/ubuntu.sh`, `src/pgprovision/_sh/os/rhel.sh`, `src/pgprovision/_sh/os/user.sh` |
| Tests | `tests/` (conftest adds `src/` to `sys.path`; tests do not require install for unit runs) |
| Packaging | `pyproject.toml` |
| CI | `.github/workflows/ci.yml`, `.github/workflows/pre-commit.yml` |
| Hooks | `.pre-commit-config.yaml` (includes a local `pytest` hook with `additional_dependencies: [pytest]`) |
| Lockfile | `uv.lock` (may be untracked) |

---

## Mission

Produce a plan that migrates **contributor and CI Python workflows** to uv:

- Declared dev dependencies (PEP 735 `[dependency-groups]` or equivalent uv-native approach).
- Committed, reproducible `uv.lock`.
- Consistent local commands: `uv sync`, `uv run pytest`, `uv run pre-commit`, `uv build`.
- CI jobs rewritten to use `astral-sh/setup-uv` (or equivalent) instead of scattered `pip install` steps.
- Publish path still produces valid sdist/wheel and gates on existing quality jobs.

**Non-goals:**

- Changing the build backend away from setuptools unless uv can wrap it without migration risk.
- Requiring end users to install uv.
- Rewriting shell provisioning logic or OS backends.
- Fedora PGDG repo fix (unless explicitly scoped as a dependency for Fedora CI smoke).

---

## Design constraints (must appear in the plan)

- **Fail fast** with actionable diagnostics; no silent fallbacks.
- **Minimize scope** — workflow/CI/docs only; smallest correct diff.
- **Break changes allowed** for contributor workflow — update all call sites to one way (no pip/uv dual paths in CI unless transitional with a hard removal step).
- **No `os.environ` / `os.getenv` in application code** (not relevant to this migration, but do not introduce config reads).
- New or changed functions need current docstrings (if any Python helper scripts are added for CI).
- Plan must specify concrete file paths and verification commands, not vague "update CI."

---

## Investigation checklist (complete before writing the plan)

Answer each with **FACT** (cited `path:Lx-Ly`) or **NOT FOUND**:

1. What is in `pyproject.toml` today? Runtime deps? Dev deps? `[tool.uv]` config?
2. What does `uv.lock` contain? Is it tracked in git?
3. Which CI jobs install Python packages and how (`pip install .`, `pip install pytest`, `python -m build`, etc.)?
4. Which jobs gate PyPI publish (`publish.needs`)?
5. What does `.pre-commit-config.yaml` assume about Python env (especially the local `pytest` hook)?
6. Does `tests/conftest.py` require editable install, or only `sys.path` injection?
7. Are there docs/orchestrator prompts that hard-code `pip` or `uv run python -m pip install -e .`?
8. What is the minimum Fedora/RHEL CI matrix that replaces Ubuntu/Rocky smoke for this operator's priorities?
9. How should Rocky container job (`rockylinux:9`) be handled — remove, replace with Fedora/RHEL UBI, or demote to non-gating?
10. Can `uv build` replace `python -m build` without changing artifacts (sdist/wheel contents, `twine check`)?

---

## Required plan structure

Mirror the house style in `docs/plans/phases-8-9-completion-plan.md`:

1. **Purpose** — one paragraph.
2. **Facts** — bullet list with `path:Lx-Ly` citations from investigation.
3. **Inferences** — risks, trade-offs, transitional concerns.
4. **Scope** — In Scope / Out of Scope tables.
5. **Requirements** — numbered, testable requirements (dev deps, lockfile policy, CI commands, docs, publish).
6. **Implementation steps** — phased (suggest 3–5 phases), each with:
   - Goal
   - Files to touch
   - Exact commands for verification gate
   - Exit criteria
   - Dependencies on prior phases
7. **Testing** — table mapping requirement → test or gate (unit pytest, pre-commit, build/twine, smoke install from wheel/sdist).
8. **CI migration matrix** — table: current job → proposed uv-based steps → gating? (yes/no) → platform (Fedora/RHEL/other).
9. **Rollout / rollback** — how to revert if CI breaks; whether a transitional dual-path is worth it (default: no).
10. **Acceptance criteria** — checkbox list the implementer can tick.
11. **Open questions** — only items you cannot resolve from the repo; keep short.

---

## CI guidance the plan must address

The plan should propose a **Fedora/RHEL-centric** CI strategy. At minimum, discuss:

| Concern | Plan must decide |
|---------|------------------|
| Unit test matrix | Keep Python 3.9–3.13 matrix with `uv run pytest`, or narrow for Fedora/RHEL tooling? |
| `pre-commit` job | `uv sync --dev` + `uv run pre-commit` vs keep `pre-commit/action` |
| Build job | `uv build` + install wheel/sdist smoke |
| OS smoke | Replace `rocky-smoke` with Fedora container dry-run? Add RHEL UBI? Self-hosted RHEL note? |
| Integration jobs | Demote/remove Ubuntu PGDG integration from publish gates? |
| Publish job | `uv build` before `gh-action-pypi-publish` |
| Caching | `setup-uv` cache vs pip cache removal |
| `SETuptools_SCM_PRETEND_VERSION` | Preserve existing env patterns in container/smoke jobs |

Do **not** assume Ubuntu integration stays in `publish.needs` unless investigation shows a strong reason.

---

## Local developer experience the plan must specify

Document the **one true path** after migration:

```bash
# Example — plan should finalize exact commands
uv sync --dev
uv run pytest -q
uv run pre-commit run --all-files
uv build
```

Clarify:

- Editable vs non-editable install for local dev and smoke tests.
- Whether `uv run pgprovision` replaces installed console script in dev.
- Whether `uv.lock` is committed (recommended: yes).
- Whether to add `.python-version` (optional; plan should decide).

---

## Verification gates (every phase in the plan)

Each phase must end with explicit gates. Minimum final gates:

```bash
uv sync --dev
uv run pytest -q
bash -n src/pgprovision/_sh/provision.sh src/pgprovision/_sh/os/*.sh
uv run pre-commit run --all-files
uv build
# smoke: install artifact and run pgprovision --dry-run (plan specifies uv pip vs pip for smoke)
```

---

## Deliverable quality bar

The plan is **rejectable** if it:

- Proposes implementation without investigating current CI/job dependencies.
- Omits `publish.needs` impact analysis.
- Keeps pip and uv side by side in CI without a removal step.
- Treats uv migration as requiring Poetry/hatch/pdm backend change without justification.
- Ignores the operator's Fedora/RHEL platform priority.
- Lacks per-phase exit criteria and verification commands.

The plan is **acceptable** if an implementer can execute it phase-by-phase without asking basic repo questions.

---

## Output reminder

Save only:

```
docs/plans/uv-migration-plan.md
```

Do not modify source files, workflows, or `pyproject.toml` while planning.
