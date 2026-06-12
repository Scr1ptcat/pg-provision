# Graph Report - pg-provision  (2026-06-11)

## Corpus Check
- 56 files · ~70,686 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1013 nodes · 1266 edges · 79 communities (59 shown, 20 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 198 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9102e315`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]

## God Nodes (most connected - your core abstractions)
1. `bash()` - 167 edges
2. `_make_valid_pgdata()` - 22 edges
3. `PostgreSQL Provisioner – RHEL/Rocky/Alma Test Guide (pgprovision)` - 19 edges
4. `PostgreSQL Provisioner – Ubuntu Test Guide (pgprovision)` - 17 edges
5. `Phases 8–9: Full Cluster Uninstall, CI, Docs, and Validation` - 14 edges
6. `uv Migration Plan` - 14 edges
7. `uv User Install Plan (RHEL/Fedora)` - 14 edges
8. `Planning prompt: migrate pg-provision development and CI to uv` - 13 edges
9. `Phases 8–9 Completion Plan` - 13 edges
10. `Default PostgreSQL Major 18 Plan` - 13 edges

## Surprising Connections (you probably didn't know these)
- `test_hba_managed_header_top_singleton_preserves_vendor()` --calls--> `bash()`  [INFERRED]
  tests/test_managed_blocks.py → tests/conftest.py
- `test_pg_ident_managed_block_entries_and_mode_preserved()` --calls--> `bash()`  [INFERRED]
  tests/test_managed_blocks.py → tests/conftest.py
- `test_replace_managed_block_preserves_mode_and_top_insertion()` --calls--> `bash()`  [INFERRED]
  tests/test_managed_blocks.py → tests/conftest.py
- `test_os_detect_ubuntu()` --calls--> `bash()`  [INFERRED]
  tests/test_os_detect.py → tests/conftest.py
- `test_os_detect_rhel_like()` --calls--> `bash()`  [INFERRED]
  tests/test_os_detect.py → tests/conftest.py

## Hyperedges (group relationships)
- **CLI Python-to-shell passthrough flow** — cli_main, cli_run_script, cli_script_path, sh_package_marker, sh_provision_script, cli_root_escalation_policy [EXTRACTED 1.00]
- **Idempotent configuration rendering surface** — sh_apply_dropin_config, sh_write_key_value_dropin, sh_load_profile_overrides, concept_dropin_idempotency, concept_tls_dropin_policy, concept_profile_override_idempotency [INFERRED 0.88]
- **Managed access and service policy surface** — sh_apply_hba_policy, sh_write_pg_ident_map, sh_replace_managed_block_top, sh_os_enable_and_start, sh_os_restart, concept_managed_block_singleton, concept_systemd_absent_pg_ctlcluster_fallback [INFERRED 0.80]
- **Implementation Roadmap Phases** — full_plan_pg18, full_plan_pgvector, full_plan_destroy, full_plan_runtime, full_plan_user_mode, full_plan_bootstrap, full_plan_uninstall, full_plan_ci [EXTRACTED 1.00]
- **Cross-OS Validation Guides** — readme_self_heal_and_guides, ubuntu_test_guide, rhel_test_guide [EXTRACTED 1.00]
- **Destructive Operations Safety Model** — full_plan_safety, full_plan_destroy, full_plan_uninstall, plan_prompt_scope_uninstall_ci [EXTRACTED 1.00]

## Communities (79 total, 20 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.33
Nodes (4): Managed block tests for hardened configuration edits (migrated).  Covers: - HBA, test_hba_managed_header_top_singleton_preserves_vendor(), test_pg_ident_managed_block_entries_and_mode_preserved(), test_replace_managed_block_preserves_mode_and_top_insertion()

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (31): Full Implementation Plan, Architecture, API Reference, Backend Contract, Test Strategy, Phase 7 Tarball Bootstrap, Phase 9 CI Integration, Phase 3 Logical Destroy, External PGDG Facts, Risks, and Timeline, Phase 1 PG18 Readiness, Phase 2 pgvector Support (+23 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (31): Idempotent PostgreSQL drop-in rendering, pg_hba policy contract, managed block singleton editing, INIT_PG_STAT_STATEMENTS gated extension initialization, PROFILE_OVERRIDES idempotent drop-in rendering, secret-safe psql file execution, provision stamp metadata contract, write_stamp psql data_directory fallback (+23 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (35): Configuration and file-behavior tests against the new pgprovision functions.  Co, write_stamp must not alter an already-existing directory’s permissions (e.g., 07, write_key_value_dropin must update an existing key in-place (sed replace)     ra, Exercise quoting and comma-separated values:     - log_line_prefix should be wri, apply_dropin_config must set core keys exactly once and be idempotent.     We ve, Ensures apply_dropin_config adds exactly one "include_dir = 'conf.d'" line,, pg_stat_statements belongs in SPL only when explicitly requested., parse_args should map common flags to variables and reject unknown flags. (+27 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (47): Acceptance Criteria, Backend contract, CI, CI validation, CLI root routing, Code gates (every PR), code:block1 (parse_args → load_env_file → runtime_init → [bootstrap if us), code:bash (uv run pytest -q) (+39 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (20): count_hba_lines(), has_hba_line(), _pattern_for(), HBA rules tests focusing on idempotency and conditional CIDR entries (migrated)., Without ALLOWED_CIDR/ALLOWED_CIDR_V6 and with ALLOW_NETWORK unset/false,     app, With SOCKET_ONLY=true, loopback TCP must be rejected while local socket     rule, When ALLOWED_CIDR_V6 is provided and TLS is enabled, ensure a hostssl rule     i, When ALLOWED_CIDR_V6 is provided and TLS is enabled, ensure a hostssl rule     i (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (16): main, _needs_root, CLI root escalation policy, _run_script, _script_path, CLI package version resolution, bash fixture, BashResult (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.2
Nodes (5): NamedTuple, BashResult, _candidate_provision_paths(), provision_sh(), Pytest fixtures and helpers for the pgprovision test suite (migrated).  - Robust

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (46): 1) **Hardened (RHEL/Rocky/Alma): socket‑only, local peer auth**, 2) **Hardened (RHEL/Rocky/Alma): loopback‑only TCP (localhost)**, 3) **Permissive (Ubuntu): listen on all interfaces for a trusted LAN**, 4) **TLS‑required server (certs pre‑positioned)**, 5) **Reproducible runs via env‑file (no secrets)**, 6) **Custom data directory + pg_stat_statements**, 7) **pgvector on PGDG PostgreSQL**, 8) **Logical destroy: drop one database and optional role** (+38 more)

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (5): pg_stat_statements initialization behavior tests.  Verifies: - Positive: when IN, Stubs sudo and psql to capture calls; asserts "sudo -u postgres", "psql",     an, With INIT_PG_STAT_STATEMENTS unset/false, there must be no sudo/psql calls., test_pgss_flag_absent_does_not_invoke(), test_pgss_flag_triggers_create_extension()

### Community 11 - "Community 11"
Cohesion: 0.43
Nodes (6): Tests for PROFILE_OVERRIDES and PROFILE-driven idempotent drop-in rendering.  Fo, _read_dropins_text(), test_load_profile_overrides_integration_and_dropin(), test_missing_explicit_profile_fails(), test_profile_overrides_idempotent_singleton(), test_profile_overrides_update_without_duplication()

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (12): _env_file_requests_user_mode(), main(), _needs_root(), Return the absolute path to a packaged shell helper script., Return true when args or root-routing env request user-mode execution., Return true when a forwarded env file requests user-mode root routing., Return true when a system-mode invocation needs sudo wrapping.      User-mode ne, Run a packaged shell script, adding sudo only for system-mode actions. (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (3): environment-dependent auto-skip, psql_available fixture, systemd_available fixture

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (3): OS_RELEASE_PATH based OS detection injection, os_detect, OS detection tests

### Community 21 - "Community 21"
Cohesion: 0.2
Nodes (10): 2. Plan vs reality, API spec at a glance, Audit basis, Baseline delta table, Current system-mode behavior baseline, External facts, Invalid investigation assumptions, Privilege touchpoint inventory (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (36): Acceptance Criteria, Apt retry helper, Backend hardening, Boolean flag consistency, Boolean normalization (recommended), CI, CI validation, CLI UX (+28 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (30): _make_valid_pgdata(), test_load_os_module_requires_uninstall_contract(), test_purge_packages_rhel_command_patterns(), test_purge_packages_ubuntu_command_patterns(), test_remove_pgdata_yes_env_file_triggers_pgdata_removal(), test_remove_pgdg_repo_rejected_in_user_mode(), test_remove_pgdg_repo_requires_purge_packages(), test_rhel_cleanup_repo_removes_gpg_keys() (+22 more)

### Community 24 - "Community 24"
Cohesion: 0.07
Nodes (26): 1. Executive summary (≤20 lines), 2. Plan vs reality, 3. Architecture, 4. API reference, 5. Phases (one section per phase — all baseline phases 1–9), 6. Cross-phase concerns, 7. Test strategy summary, 8. Risks and open questions (+18 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (25): A. OPERATING DOCTRINE — context hygiene + delegation (read twice), Active phases — implement from here, B. Authoritative grounding (verified 2026-06-10 — trust but re-verify before acting), C. Operator decisions, Closed phases — verify only on resume, Code anchors (current), code:block1 (SUBAGENT RESULT), code:block2 (# pg-provision full implementation — orchestrator STATE  (ov) (+17 more)

### Community 26 - "Community 26"
Cohesion: 0.1
Nodes (24): test_destroy_confirmation_env_file_can_confirm_final_destroy_db(), test_destroy_confirmation_env_is_pgprovision_confirm_destroy_db(), test_destroy_confirmation_validated_after_env_file(), test_destroy_current_user_ignores_psql_stderr_warnings(), test_destroy_dry_run_can_print_follow_on_provision_manifest(), test_destroy_dry_run_prints_manifest_without_psql(), test_destroy_only_exits_after_destroy(), test_destroy_psql_uses_configured_port() (+16 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (24): _fake_pg_bin(), _fake_pg_tarball(), _make_extension_control(), _make_valid_pgdata(), test_user_admin_failure_skips_disable_postgres_login(), test_user_admin_paths_fail_fast_on_psql_error(), test_user_admin_paths_use_runtime_psql_without_sudo(), test_user_backend_defines_full_phase5_contract() (+16 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (22): A. OPERATING DOCTRINE — context hygiene + delegation (read twice), B. Authoritative grounding (verified 2026-06-11 — trust but re-verify before acting), C. Operator decisions, code:block1 (SUBAGENT RESULT), code:bash (uv run pytest -q tests/test_uninstall_cluster.py tests/test_), code:block3 (# Phases 8–9 completion — orchestrator STATE  (overwrite eac), D. Load-bearing corrections (read first, non-negotiable), E. Phase-by-phase dispatch (detail lives in plan §Implementation Steps / §Testing) (+14 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (21): A. OPERATING DOCTRINE — context hygiene + delegation (read twice), B. Authoritative grounding (verified 2026-06-10 — trust but re-verify before acting), C. Operator decisions, code:block1 (SUBAGENT RESULT), code:block2 (# pg-provision Phases 8–9 — orchestrator STATE  (overwrite e), D. Load-bearing corrections (read first, non-negotiable), E. Phase-by-phase dispatch (detail lives in plan §Implementation Steps / §Testing), F. Traceability: LEDGER + STATE.md (maintain continuously) (+13 more)

### Community 30 - "Community 30"
Cohesion: 0.1
Nodes (20): A. OPERATING DOCTRINE — context hygiene + delegation (read twice), B. Authoritative grounding (verified 2026-06-10 — trust but re-verify before acting), C. Operator decisions, code:block1 (SUBAGENT RESULT), code:block2 (# pg-provision full implementation — orchestrator STATE  (ov), D. Load-bearing corrections (read first, non-negotiable), E. Phase-by-phase dispatch (detail lives in plan §5), F. Traceability: LEDGER + STATE.md (maintain continuously) (+12 more)

### Community 31 - "Community 31"
Cohesion: 0.11
Nodes (30): bash(), Run `bash -lc` with provision.sh sourced, returning (stdout, stderr, rc).     De, Run `bash -lc` with provision.sh sourced, returning (stdout, stderr, rc).     De, test_cli_user_mode_cannot_be_disabled_by_env_file(), test_destroy_cli_destroy_only_cannot_be_disabled_by_env_file(), test_destroy_cli_dry_run_cannot_be_disabled_by_env_file(), test_destroy_continue_validates_profile_before_sql(), test_destroy_dry_run_continue_validates_profile_before_manifest() (+22 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (20): _fake_pg_bin(), _make_extension_control(), pgvector package and extension initialization behavior tests., Without INIT_PGVECTOR=true, no psql invocation occurs., System backends should install the PGDG pgvector package for the active major., pgvector is only supported through the verified PGDG package paths., load_os_module should reject backends missing the extension package hook., INIT_PGVECTOR=true should create the vector extension in the target DB. (+12 more)

### Community 33 - "Community 33"
Cohesion: 0.11
Nodes (19): 5. Phases (one section per phase — all baseline phases 1–9), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail) (+11 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (15): 0) Prerequisites, 1) Dry‑run smoke test, 5.5) Logical destroy safety smoke, 5) User and database creation, 8) Custom data directory relocation, 9) Stamp file & permissions, code:bash (pip install pg-provision), code:bash (pgprovision --create-user devuser --create-password 'pAs$123) (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.14
Nodes (13): code:bash (# Repo root), Investigation checklist (do this before writing the report), Investigation prompt: user-mode backend + PG 18 + pgvector + destroy DB, Out of scope for this investigation, Required output format, Scope (four workstreams), Starter commands for the investigator, Success criteria (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.05
Nodes (55): 0) Prerequisites, 10) Restart sanity, 11) Self-heal: missing/invalid PGDATA (fresh create), 12) Self-heal: adopt existing valid PGDATA, 1.5) User-mode smoke (no sudo), 1) Dry‑run smoke test, 2) Full install (PGDG repo, packages, cluster, service), 3) HBA policy (+47 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (10): code:bash (cd /home/tanarus/Repositories/pg-provision), code:bash (uv run pytest -q tests/test_uninstall_cluster.py tests/test_), code:bash (uv run pytest -q), code:bash (set -euxo pipefail), First, re-ground, Fresh-session handoff: recheck skipped user-mode live validation, Goal, Re-run the skipped user-mode live gate (+2 more)

### Community 38 - "Community 38"
Cohesion: 0.38
Nodes (10): _make_fake_pg_tarball(), _nonroot_id_stub(), test_bootstrap_extracts_bin_dir(), test_bootstrap_only_exits_before_provision(), test_bootstrap_rejects_checksum_mismatch(), test_bootstrap_rejects_system_mode(), test_bootstrap_requires_sha256_for_local_file(), test_bootstrap_requires_sha256_for_url() (+2 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (32): Acceptance criteria, Additional facts, CI migration matrix, code:bash (# After editing pyproject.toml), code:bash (uv sync --dev), code:yaml (- uses: actions/checkout@v4), code:yaml (- uses: actions/checkout@v4), code:yaml (- uses: actions/checkout@v4) (+24 more)

### Community 40 - "Community 40"
Cohesion: 0.29
Nodes (6): 11) Self-heal: broken metadata, missing datadir, 12) Self-heal: adopt existing valid PGDATA, code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), code:bash (set -euxo pipefail), Run as root or with sudo.

### Community 41 - "Community 41"
Cohesion: 0.29
Nodes (7): 3.1 View managed block, 3.2 Socket‑only posture, 3.3 Allow networks, 3) HBA policy, code:bash (HBA="/etc/postgresql/${PGV}/main/pg_hba.conf"), code:bash (pgprovision --socket-only), code:bash (pgprovision --allow-network --allowed-cidr "10.0.0.0/8, 192.)

### Community 42 - "Community 42"
Cohesion: 0.33
Nodes (5): Acceptance criteria, Evidence, pg-provision Phases 8-9 final report, Remaining operator action, Status

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (31): Acceptance criteria, CI matrix (target state), code:bash (curl -LsSf https://astral.sh/uv/install.sh | sh), code:bash (# doc review only — spot-check examples match flag names in ), code:yaml (- uses: actions/checkout@v4), code:yaml (- name: Install wheel and smoke), code:bash (PGPROVISION_BIN="$(command -v pgprovision)"), code:bash (rg 'pip install pg-provision' README.md docs/test-plan-rhel.) (+23 more)

### Community 44 - "Community 44"
Cohesion: 0.08
Nodes (24): A. OPERATING DOCTRINE — context hygiene + delegation (read twice), B. Authoritative grounding (verified 2026-06-11 — trust but re-verify before acting), C. Operator decisions, code:block1 (SUBAGENT RESULT), code:bash (#!/usr/bin/env bash), code:bash (uv sync --dev), code:block4 (# uv user install (RHEL/Fedora) — orchestrator STATE  (overw), code:bash (uv sync --dev && uv run pytest -q && uv run pre-commit run -) (+16 more)

### Community 45 - "Community 45"
Cohesion: 0.33
Nodes (6): Cleanup (optional), code:bash (PREVIEW_LOG=./pgprov_uninstall_preview.log), code:bash (PREVIEW_LOG=./pgprov_uninstall_full_preview.log), code:bash (systemctl stop "postgresql@${PGV}-main" || true), Full teardown, including PGDATA and packages, Preserve PGDATA, remove cluster service metadata

### Community 46 - "Community 46"
Cohesion: 0.08
Nodes (25): 1. Centralize the default (recommended), 2. Update all fallback sites, 3. Update usage examples, 4. Add default-version test, 5. Do not blanket-update version-specific tests, CI Changes, code:bash (PGPROVISION_DEFAULT_PG_VERSION="${PGPROVISION_DEFAULT_PG_VER), code:bash (parse_args --dry-run) (+17 more)

### Community 47 - "Community 47"
Cohesion: 0.4
Nodes (5): 7.1 Guardrail (should fail without cert/key), 7.2 Self-signed certs and TLS enablement, 7) TLS guardrail and enablement, code:bash (set +e), code:bash (DATA_DIR=$(sudo -u postgres psql -At -c "SHOW data_directory)

### Community 48 - "Community 48"
Cohesion: 0.4
Nodes (4): Unit tests for os_detect via OS_RELEASE_PATH injection., test_os_detect_rhel_like(), test_os_detect_ubuntu(), test_os_detect_unsupported()

### Community 49 - "Community 49"
Cohesion: 0.4
Nodes (4): test_is_valid_pgdata_accepts_symlinked_wal(), test_is_valid_pgdata_fails_when_core_piece_missing(), test_ubuntu_relocation_refuses_to_drop_valid_pgdata(), test_ubuntu_relocation_uses_elevated_pgdata_validation()

### Community 50 - "Community 50"
Cohesion: 0.4
Nodes (4): Security behavior tests for secret handling in create_db_and_user.  Ensures pass, test_create_db_without_create_user_omits_owner(), test_create_user_password_from_file(), test_create_user_password_not_in_argv()

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): Acceptance criteria, Notes, Outcome, Phase results, uv user install (RHEL/Fedora) — FINAL REPORT

### Community 52 - "Community 52"
Cohesion: 0.83
Nodes (3): _make_stub(), test_os_enable_and_start_fallback_without_systemd(), test_os_restart_fallback_without_systemd()

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (8): 1. Executive summary, 7. Test strategy summary, 8. Risks and open questions, 9. Implementation order and timeline, CI job matrix, Execution checklist, Manual VM matrix, Unit tests

### Community 56 - "Community 56"
Cohesion: 0.67
Nodes (3): 2) Full install (PGDG repo, packages, cluster, service), code:bash (pgprovision --pg-version "${PGV}" | tee ./pgprov_install.log), code:bash (systemctl status "postgresql@${PGV}-main" --no-pager -l || t)

### Community 57 - "Community 57"
Cohesion: 0.67
Nodes (3): code:bash (sudo rm -f /tmp/pgprov_install.log), code:bash (systemctl status "postgresql@${PGV}-main" --no-pager -l), Troubleshooting

### Community 67 - "Community 67"
Cohesion: 0.22
Nodes (9): 3. Architecture, Backend contract end state, Backend contract progression, code:mermaid (flowchart TD), code:mermaid (flowchart TD), code:mermaid (flowchart LR), Logical destroy vs full uninstall, System vs user-mode dispatch (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.29
Nodes (7): 4. API reference, Existing flags/env whose behavior changes, New full uninstall flags/env, New logical destroy flags/env, New pgvector flags/env, New tarball bootstrap flags/env, New user-mode flags/env

### Community 69 - "Community 69"
Cohesion: 0.29
Nodes (7): 6. Cross-phase concerns, CI cost/latency tradeoffs, code:bash (runtime_init()                 # mode, dry-run, sudo array, ), Conditional `shared_preload_libraries` migration, Destroy vs uninstall safety philosophy, `runtime.sh` API sketch, User-mode feature parity matrix

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (17): CI guidance the plan must address, code:block1 (docs/plans/uv-migration-plan.md), code:bash (# Example — plan should finalize exact commands), code:bash (uv sync --dev), code:block4 (docs/plans/uv-migration-plan.md), Deliverable quality bar, Design constraints (must appear in the plan), Investigation checklist (complete before writing the plan) (+9 more)

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (17): provision.sh argument parsing contract, PGDATA validity contract, RHEL self-heal noop when unit is missing, SELF_HEAL default enabled flag, pg_ctlcluster fallback when systemd is absent, _make_stub for RHEL self-heal tests, _make_stub for service fallback tests, _is_valid_pgdata (+9 more)

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Acceptance criteria, Additional maintenance, Outcome, Phase results, Phases 8-9 completion FINAL REPORT, Required next action

## Knowledge Gaps
- **440 isolated node(s):** `Return the absolute path to a packaged shell helper script.`, `Return true when args or root-routing env request user-mode execution.`, `Return true when a forwarded env file requests user-mode root routing.`, `Return true when a system-mode invocation needs sudo wrapping.      User-mode ne`, `Run a packaged shell script, adding sudo only for system-mode actions.` (+435 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `bash()` connect `Community 31` to `Community 0`, `Community 3`, `Community 5`, `Community 7`, `Community 10`, `Community 11`, `Community 15`, `Community 23`, `Community 26`, `Community 27`, `Community 32`, `Community 38`, `Community 48`, `Community 49`, `Community 50`, `Community 52`, `Community 58`, `Community 59`, `Community 60`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `test_apply_dropin_escapes_single_quotes_in_strings()` connect `Community 3` to `Community 31`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 164 inferred relationships involving `bash()` (e.g. with `test_include_dir_idempotent()` and `test_tls_dropin_writes_ssl_options()`) actually correct?**
  _`bash()` has 164 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Return the absolute path to a packaged shell helper script.`, `Return true when args or root-routing env request user-mode execution.`, `Return true when a forwarded env file requests user-mode root routing.` to the rest of the system?**
  _440 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._