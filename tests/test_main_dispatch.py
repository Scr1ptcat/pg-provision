import pytest


@pytest.mark.unit
def test_destroy_dry_run_skips_self_heal_and_mutations(bash):
    r = bash(
        """
      provision_psql() { echo "psql called"; return 99; }
      os_detect() { echo "os_detect called"; return 99; }
      load_os_module() { echo "load_os_module called"; return 99; }
      _ubuntu_self_heal_cluster() { echo "self_heal called"; return 99; }
      os_prepare_repos() { echo "os_prepare_repos called"; return 99; }
      main --destroy-db appdb --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Logical destroy manifest" in r.stdout
    assert "Provision dry-run manifest" in r.stdout
    assert "psql called" not in r.stdout
    assert "os_detect called" not in r.stdout
    assert "load_os_module called" not in r.stdout
    assert "self_heal called" not in r.stdout
    assert "os_prepare_repos called" not in r.stdout


@pytest.mark.unit
def test_destroy_cli_dry_run_cannot_be_disabled_by_env_file(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text(
        "DRY_RUN=false\nDESTROY_DB=envdb\nPGPROVISION_CONFIRM_DESTROY_DB=envdb\n",  # pragma: allowlist secret
        encoding="utf-8",
    )

    r = bash(
        """
      provision_psql() { echo "psql called"; return 99; }
      main --destroy-db clidb --confirm-destroy-db clidb --dry-run --env-file "$ENVF"
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr
    assert "destroy_db: envdb" in r.stdout
    assert "dry_run: true" in r.stdout
    assert "psql called" not in r.stdout


@pytest.mark.unit
def test_destroy_cli_destroy_only_cannot_be_disabled_by_env_file(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("DESTROY_ONLY=false\n", encoding="utf-8")

    r = bash(
        """
      require_root_or_sudo() { :; }
      id() { if [[ "${1:-}" == "-u" ]]; then echo 0; else command id "$@"; fi; }
      provision_psql() {
        case "$*" in
          *"SELECT 1;"*) return 0 ;;
          *"SELECT current_user;"*) printf '%s\n' postgres; return 0 ;;
        esac
        cat >/dev/null
      }
      os_detect() { echo "os_detect called"; return 99; }
      main --destroy-db appdb --confirm-destroy-db appdb --destroy-only --env-file "$ENVF"
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr
    assert "continue_provision: false" in r.stdout
    assert "os_detect called" not in r.stdout


@pytest.mark.unit
def test_destroy_continue_validates_profile_before_sql(bash):
    r = bash(
        """
      id() { if [[ "${1:-}" == "-u" ]]; then echo 0; else command id "$@"; fi; }
      provision_psql() { echo "psql called"; return 99; }
      main --destroy-db appdb --confirm-destroy-db appdb --profile missing-phase4-profile
        """
    )

    assert r.rc == 2
    assert "Profile not found" in r.stderr
    assert "psql called" not in r.stdout


@pytest.mark.unit
def test_destroy_dry_run_continue_validates_profile_before_manifest(bash):
    r = bash(
        """
      provision_psql() { echo "psql called"; return 99; }
      main --destroy-db appdb --dry-run --profile missing-phase4-profile
        """
    )

    assert r.rc == 2
    assert "Profile not found" in r.stderr
    assert "Logical destroy manifest" not in r.stdout
    assert "psql called" not in r.stdout


@pytest.mark.unit
def test_provision_dry_run_allows_read_only_discovery(bash):
    r = bash(
        """
      os_detect() { echo "read-only os_detect"; OS_FAMILY=ubuntu; }
      load_os_module() { echo "read-only load_os_module"; }
      main --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "read-only os_detect" in r.stdout
    assert "read-only load_os_module" in r.stdout
    assert "Provision dry-run manifest" in r.stdout
    assert "os_family: ubuntu" in r.stdout


@pytest.mark.unit
def test_user_mode_dry_run_bypasses_os_detect_and_defaults_repo_none(bash):
    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      os_detect() { echo "os_detect called"; return 99; }
      main --user-mode --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Provision dry-run manifest" in r.stdout
    assert "os_family: user" in r.stdout
    assert "repo: none" in r.stdout
    assert "os_detect called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_user_mode_dry_run_rejects_system_repo(bash):
    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      os_detect() { echo "os_detect called"; return 99; }
      main --user-mode --dry-run --repo pgdg
        """
    )

    assert r.rc == 2
    assert "cannot prepare --repo pgdg" in r.stderr
    assert "Provision dry-run manifest" not in r.stdout
    assert "os_detect called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_user_mode_defaults_clear_admin_group_role(bash):
    r = bash(
        """
      parse_args --user-mode
      resolve_mode_defaults
      printf 'admin_group=%s\n' "${ADMIN_GROUP_ROLE:-}"
        """
    )

    assert r.rc == 0, r.stderr
    assert "admin_group=" in r.stdout
    assert "dba_group" not in r.stdout


@pytest.mark.unit
def test_user_mode_respects_explicit_empty_socket_and_admin_env(bash):
    r = bash(
        """
      main --dry-run
        """,
        env={
            "PGPROVISION_MODE": "user",
            "UNIX_SOCKET_GROUP": "",
            "ADMIN_GROUP_ROLE": "",
        },
    )

    assert r.rc == 0, r.stderr
    assert "Provision dry-run manifest" in r.stdout
    assert "os_family: user" in r.stdout


@pytest.mark.unit
def test_user_mode_truthy_env_matches_cli_case_handling(bash):
    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      os_detect() { echo "os_detect called"; return 99; }
      main --dry-run
        """,
        env={"USER_MODE": "True"},
    )

    assert r.rc == 0, r.stderr
    assert "os_family: user" in r.stdout
    assert "os_detect called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_cli_user_mode_cannot_be_disabled_by_env_file(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("PGPROVISION_MODE=system\nUSER_MODE=false\n", encoding="utf-8")

    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      os_detect() { echo "os_detect called"; return 99; }
      main --user-mode --dry-run --env-file "$ENVF"
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr
    assert "os_family: user" in r.stdout
    assert "os_detect called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_user_mode_allows_explicit_admin_group_role(bash):
    r = bash(
        """
      parse_args --user-mode --admin-group-role dba_group
      resolve_mode_defaults
      validate_user_mode_mvp_limits
      printf 'admin_group=%s\n' "$ADMIN_GROUP_ROLE"
        """
    )

    assert r.rc == 0, r.stderr
    assert "admin_group=dba_group" in r.stdout


@pytest.mark.unit
def test_user_mode_admin_dbrole_requires_admin_group_role(bash):
    r = bash(
        """
      parse_args --user-mode --admin-dbrole dba
      resolve_mode_defaults
      validate_user_mode_mvp_limits
        """
    )

    assert r.rc == 2
    assert "--admin-dbrole requires" in r.stderr


@pytest.mark.unit
def test_user_mode_real_run_bypasses_sudo_and_root_requirement(tmp_path, bash):
    data = tmp_path / "data"
    conf = data / "postgresql.conf"
    hba = data / "pg_hba.conf"
    ident = data / "pg_ident.conf"
    data.mkdir()
    conf.touch()
    hba.touch()
    ident.touch()

    r = bash(
        """
      sudo() { echo "sudo called"; return 99; }
      id() { if [[ "${1:-}" == "-u" ]]; then echo 1000; else command id "$@"; fi; }
      os_detect() { echo "os_detect called"; return 99; }
      load_os_module() {
        echo "load_os_module OS=${OS_FAMILY}"
        os_self_heal() { :; }
        os_prepare_repos() { :; }
        os_install_packages() { :; }
        os_install_extension_packages() { :; }
        os_init_cluster() { :; }
        os_get_paths() {
          printf 'CONF_FILE=%q HBA_FILE=%q IDENT_FILE=%q DATA_DIR=%q SERVICE=%q LOG_FILE=%q UNIX_SOCKET_DIR=%q\n' \
            "${CONF:?}" "${HBA:?}" "${IDENT:?}" "${DATA:?}" "user:${DATA:?}" "${LOG:?}" "${SOCKET:?}"
        }
        os_restart() { echo "restart $*"; }
      }
      assert_psql_major_matches() { :; }
      apply_dropin_config() { echo "dropin $*"; }
      ensure_socket_group_and_members() { :; }
      apply_hba_policy() { echo "hba $*"; }
      write_pg_ident_map() { echo "ident $*"; }
      conditionally_init_pg_stat_statements() { :; }
      setup_role_mappings_and_admin() { :; }
      create_db_and_user() { :; }
      conditionally_init_pgvector() { :; }
      write_stamp() { echo "stamp $*"; }
      main --user-mode --data-dir "${DATA:?}"
        """,
        env={
            "DATA": str(data),
            "CONF": str(conf),
            "HBA": str(hba),
            "IDENT": str(ident),
            "LOG": str(tmp_path / "postgresql.log"),
            "SOCKET": str(tmp_path / "run"),
        },
    )

    assert r.rc == 0, r.stderr
    assert "load_os_module OS=user" in r.stdout
    assert "os_detect called" not in r.stdout
    assert "sudo called" not in r.stdout


@pytest.mark.unit
def test_provision_dry_run_skips_self_heal_and_mutations(bash):
    r = bash(
        """
      os_detect() { OS_FAMILY=ubuntu; }
      load_os_module() { :; }
      _ubuntu_self_heal_cluster() { echo "self_heal called"; return 99; }
      _rhel_self_heal_cluster() { echo "rhel_self_heal called"; return 99; }
      os_prepare_repos() { echo "os_prepare_repos called"; return 99; }
      os_install_packages() { echo "os_install_packages called"; return 99; }
      os_install_extension_packages() { echo "os_install_extension_packages called"; return 99; }
      os_init_cluster() { echo "os_init_cluster called"; return 99; }
      apply_dropin_config() { echo "apply_dropin_config called"; return 99; }
      apply_hba_policy() { echo "apply_hba_policy called"; return 99; }
      create_db_and_user() { echo "create_db_and_user called"; return 99; }
      main --dry-run
        """
    )

    assert r.rc == 0, r.stderr
    assert "Provision dry-run manifest" in r.stdout
    assert "self_heal called" not in r.stdout
    assert "rhel_self_heal called" not in r.stdout
    assert "os_prepare_repos called" not in r.stdout
    assert "os_install_packages called" not in r.stdout
    assert "os_install_extension_packages called" not in r.stdout
    assert "os_init_cluster called" not in r.stdout
    assert "apply_dropin_config called" not in r.stdout
    assert "apply_hba_policy called" not in r.stdout
    assert "create_db_and_user called" not in r.stdout


@pytest.mark.unit
def test_provision_cli_dry_run_cannot_be_disabled_by_env_file(tmp_path, bash):
    env_file = tmp_path / "pgprovision.env"
    env_file.write_text("DRY_RUN=false\n", encoding="utf-8")

    r = bash(
        """
      os_detect() { OS_FAMILY=ubuntu; }
      load_os_module() { :; }
      os_prepare_repos() { echo "os_prepare_repos called"; return 99; }
      os_install_packages() { echo "os_install_packages called"; return 99; }
      os_init_cluster() { echo "os_init_cluster called"; return 99; }
      main --dry-run --env-file "$ENVF"
        """,
        env={"ENVF": str(env_file)},
    )

    assert r.rc == 0, r.stderr
    assert "Provision dry-run manifest" in r.stdout
    assert "os_prepare_repos called" not in r.stdout
    assert "os_install_packages called" not in r.stdout
    assert "os_init_cluster called" not in r.stdout
