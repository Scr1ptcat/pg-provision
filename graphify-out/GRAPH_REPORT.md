# Graph Report - . (2026-06-10)

## Corpus Check

- Corpus is ~20,557 words - fits in a single context window. You may not need a graph.

## Summary

- 214 nodes · 274 edges · 21 communities (16 shown, 5 thin omitted)
- Extraction: 74% EXTRACTED · 26% INFERRED · 0% AMBIGUOUS · INFERRED: 71 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)

- \[[\_COMMUNITY_Bash Test Harness|Bash Test Harness]\]
- \[[\_COMMUNITY_Implementation Roadmap|Implementation Roadmap]\]
- \[[\_COMMUNITY_Provisioning Configuration Policies|Provisioning Configuration Policies]\]
- \[[\_COMMUNITY_Drop-in Config Tests|Drop-in Config Tests]\]
- \[[\_COMMUNITY_Runtime Service Contracts|Runtime Service Contracts]\]
- \[[\_COMMUNITY_HBA Policy Tests|HBA Policy Tests]\]
- \[[\_COMMUNITY_CLI Execution Flow|CLI Execution Flow]\]
- \[[\_COMMUNITY_Pytest Fixture Harness|Pytest Fixture Harness]\]
- \[[\_COMMUNITY_Secret Stamp Handling|Secret Stamp Handling]\]
- \[[\_COMMUNITY_CLI Sudo Tests|CLI Sudo Tests]\]
- \[[\_COMMUNITY_pg_stat_statements Tests|pg_stat_statements Tests]\]
- \[[\_COMMUNITY_Profile Override Tests|Profile Override Tests]\]
- \[[\_COMMUNITY_CLI Helper Functions|CLI Helper Functions]\]
- \[[\_COMMUNITY_Environment Skip Fixtures|Environment Skip Fixtures]\]
- \[[\_COMMUNITY_OS Detection Injection|OS Detection Injection]\]
- \[[\_COMMUNITY_Drop-in Idempotency Test|Drop-in Idempotency Test]\]
- \[[\_COMMUNITY_Package Metadata|Package Metadata]\]
- \[[\_COMMUNITY_Pytest Marker Registration|Pytest Marker Registration]\]
- \[[\_COMMUNITY_Line Parsing Helper|Line Parsing Helper]\]

## God Nodes (most connected - your core abstractions)

1. `bash()` - 39 edges
1. `apply_dropin_config` - 7 edges
1. `has_hba_line()` - 6 edges
1. `count_hba_lines()` - 6 edges
1. `Phase 8 Full Cluster Uninstall` - 6 edges
1. `test_hba_adds_ipv4_cidr_without_tls()` - 5 edges
1. `test_hba_adds_ipv4_cidr_with_tls_hostssl()` - 5 edges
1. `test_hba_ipv6_allow_with_tls()` - 5 edges
1. `_run_script` - 5 edges
1. `Idempotent PostgreSQL drop-in rendering` - 5 edges

## Surprising Connections (you probably didn't know these)

- `CLI sudo policy tests` --conceptually_related_to--> `_needs_root` [INFERRED]
  tests/test_cli.py → src/pgprovision/cli.py
- `CLI sudo policy tests` --conceptually_related_to--> `CLI root escalation policy` [INFERRED]
  tests/test_cli.py → src/pgprovision/cli.py
- `test_include_dir_idempotent()` --calls--> `bash()` [INFERRED]
  tests/test_config.py → tests/conftest.py
- `test_tls_dropin_writes_ssl_options()` --calls--> `bash()` [INFERRED]
  tests/test_config.py → tests/conftest.py
- `test_tls_disabled_has_no_ssl_options()` --calls--> `bash()` [INFERRED]
  tests/test_config.py → tests/conftest.py

## Hyperedges (group relationships)

- **CLI Python-to-shell passthrough flow** — cli_main, cli_run_script, cli_script_path, sh_package_marker, sh_provision_script, cli_root_escalation_policy [EXTRACTED 1.00]
- **Idempotent configuration rendering surface** — sh_apply_dropin_config, sh_write_key_value_dropin, sh_load_profile_overrides, concept_dropin_idempotency, concept_tls_dropin_policy, concept_profile_override_idempotency [INFERRED 0.88]
- **Managed access and service policy surface** — sh_apply_hba_policy, sh_write_pg_ident_map, sh_replace_managed_block_top, sh_os_enable_and_start, sh_os_restart, concept_managed_block_singleton, concept_systemd_absent_pg_ctlcluster_fallback [INFERRED 0.80]
- **Implementation Roadmap Phases** — full_plan_pg18, full_plan_pgvector, full_plan_destroy, full_plan_runtime, full_plan_user_mode, full_plan_bootstrap, full_plan_uninstall, full_plan_ci [EXTRACTED 1.00]
- **Cross-OS Validation Guides** — readme_self_heal_and_guides, ubuntu_test_guide, rhel_test_guide [EXTRACTED 1.00]
- **Destructive Operations Safety Model** — full_plan_safety, full_plan_destroy, full_plan_uninstall, plan_prompt_scope_uninstall_ci [EXTRACTED 1.00]

## Communities (21 total, 5 thin omitted)

### Community 0 - "Bash Test Harness"

Cohesion: 0.08
Nodes (24): bash(), Run `bash -lc` with provision.sh sourced, returning (stdout, stderr, rc). De, Managed block tests for hardened configuration edits (migrated). Covers: - HBA, test_hba_managed_header_top_singleton_preserves_vendor(), test_pg_ident_managed_block_entries_and_mode_preserved(), test_replace_managed_block_preserves_mode_and_top_insertion(), Unit tests for os_detect via OS_RELEASE_PATH injection., test_os_detect_rhel_like() (+16 more)

### Community 1 - "Implementation Roadmap"

Cohesion: 0.09
Nodes (31): Full Implementation Plan, Architecture, API Reference, Backend Contract, Test Strategy, Phase 7 Tarball Bootstrap, Phase 9 CI Integration, Phase 3 Logical Destroy, External PGDG Facts, Risks, and Timeline, Phase 1 PG18 Readiness, Phase 2 pgvector Support (+23 more)

### Community 2 - "Provisioning Configuration Policies"

Cohesion: 0.11
Nodes (24): Idempotent PostgreSQL drop-in rendering, pg_hba policy contract, managed block singleton editing, INIT_PG_STAT_STATEMENTS gated extension initialization, PROFILE_OVERRIDES idempotent drop-in rendering, TLS drop-in configuration policy, count_hba_lines, has_hba_line (+16 more)

### Community 3 - "Drop-in Config Tests"

Cohesion: 0.1
Nodes (19): Configuration and file-behavior tests against the new pgprovision functions. Co, write_stamp must not alter an already-existing directory’s permissions (e.g., 07, write_key_value_dropin must update an existing key in-place (sed replace) ra, Exercise quoting and comma-separated values: - log_line_prefix should be wri, apply_dropin_config must set core keys exactly once and be idempotent. We ve, Ensures apply_dropin_config adds exactly one "include_dir = 'conf.d'" line,, parse_args should map common flags to variables and reject unknown flags., apply_dropin_config must safely escape single quotes in quoted string values (+11 more)

### Community 4 - "Runtime Service Contracts"

Cohesion: 0.13
Nodes (17): provision.sh argument parsing contract, PGDATA validity contract, RHEL self-heal noop when unit is missing, SELF_HEAL default enabled flag, pg_ctlcluster fallback when systemd is absent, \_make_stub for RHEL self-heal tests, \_make_stub for service fallback tests, \_is_valid_pgdata (+9 more)

### Community 5 - "HBA Policy Tests"

Cohesion: 0.19
Nodes (16): count_hba_lines(), has_hba_line(), \_pattern_for(), HBA rules tests focusing on idempotency and conditional CIDR entries (migrated)., Without ALLOWED_CIDR/ALLOWED_CIDR_V6 and with ALLOW_NETWORK unset/false, app, With SOCKET_ONLY=true, loopback TCP must be rejected while local socket rule, When ALLOWED_CIDR_V6 is provided and TLS is enabled, ensure a hostssl rule i, apply_hba_policy must ensure exactly one of each default entry: - local al (+8 more)

### Community 6 - "CLI Execution Flow"

Cohesion: 0.17
Nodes (16): main, \_needs_root, CLI root escalation policy, \_run_script, \_script_path, CLI package version resolution, bash fixture, BashResult (+8 more)

### Community 7 - "Pytest Fixture Harness"

Cohesion: 0.2
Nodes (5): NamedTuple, BashResult, \_candidate_provision_paths(), provision_sh(), Pytest fixtures and helpers for the pgprovision test suite (migrated). - Robust

### Community 8 - "Secret Stamp Handling"

Cohesion: 0.33
Nodes (7): secret-safe psql file execution, provision stamp metadata contract, write_stamp psql data_directory fallback, create_db_and_user, write_stamp, database/user secret handling tests, write_stamp psql fallback test

### Community 10 - "pg_stat_statements Tests"

Cohesion: 0.33
Nodes (5): pg_stat_statements initialization behavior tests. Verifies: - Positive: when IN, Stubs sudo and psql to capture calls; asserts "sudo -u postgres", "psql", an, With INIT_PG_STAT_STATEMENTS unset/false, there must be no sudo/psql calls., test_pgss_flag_absent_does_not_invoke(), test_pgss_flag_triggers_create_extension()

### Community 11 - "Profile Override Tests"

Cohesion: 0.53
Nodes (5): Tests for PROFILE_OVERRIDES and PROFILE-driven idempotent drop-in rendering. Fo, \_read_dropins_text(), test_load_profile_overrides_integration_and_dropin(), test_profile_overrides_idempotent_singleton(), test_profile_overrides_update_without_duplication()

### Community 12 - "CLI Helper Functions"

Cohesion: 0.7
Nodes (4): main(), \_needs_root(), \_run_script(), \_script_path()

### Community 13 - "Environment Skip Fixtures"

Cohesion: 0.67
Nodes (3): environment-dependent auto-skip, psql_available fixture, systemd_available fixture

### Community 14 - "OS Detection Injection"

Cohesion: 1.0
Nodes (3): OS_RELEASE_PATH based OS detection injection, os_detect, OS detection tests

## Knowledge Gaps

- **53 isolated node(s):** `Pytest fixtures and helpers for the pgprovision test suite (migrated).  - Robust`, `Run `bash -lc` with provision.sh sourced, returning (stdout, stderr, rc).     De`, `Configuration and file-behavior tests against the new pgprovision functions.  Co`, `Ensures apply_dropin_config adds exactly one "include_dir = 'conf.d'" line,`, `When ENABLE_TLS=true, apply_dropin_config must write expected TLS settings     i` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (\<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions

_Questions this graph is uniquely positioned to answer:_

- **Why does `bash()` connect `Bash Test Harness` to `Drop-in Config Tests`, `HBA Policy Tests`, `Pytest Fixture Harness`, `pg_stat_statements Tests`, `Profile Override Tests`, `Drop-in Idempotency Test`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Why does `configuration behavior tests` connect `Provisioning Configuration Policies` to `Secret Stamp Handling`, `Runtime Service Contracts`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `parse_args` connect `Runtime Service Contracts` to `Provisioning Configuration Policies`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `bash()` (e.g. with `test_include_dir_idempotent()` and `test_tls_dropin_writes_ssl_options()`) actually correct?**
  _`bash()` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `apply_dropin_config` (e.g. with `Idempotent PostgreSQL drop-in rendering` and `TLS drop-in configuration policy`) actually correct?**
  _`apply_dropin_config` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Pytest fixtures and helpers for the pgprovision test suite (migrated).  - Robust`, `Run `bash -lc` with provision.sh sourced, returning (stdout, stderr, rc).     De`, `Configuration and file-behavior tests against the new pgprovision functions.  Co` to the rest of the system?**
  _53 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Bash Test Harness` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
