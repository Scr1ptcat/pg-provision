#!/usr/bin/env bash
# User-mode backend for preinstalled PostgreSQL binaries.

: "${PG_VERSION:=16}"
: "${REPO_KIND:=none}"

_user_base_dir() {
	runtime_user_base_dir
}

_user_runtime_dir() {
	runtime_user_runtime_dir
}

_user_data_dir() {
	if [[ -n "${DATA_DIR:-}" && "${DATA_DIR}" != "auto" ]]; then
		printf '%s\n' "$DATA_DIR"
	else
		printf '%s\n' "$(_user_base_dir)/data"
	fi
}

_user_log_file() {
	if [[ -n "${LOG_FILE:-}" ]]; then
		printf '%s\n' "$LOG_FILE"
	else
		printf '%s\n' "$(_user_base_dir)/log/postgresql.log"
	fi
}

_user_pg_bin_dir() {
	runtime_resolve_pg_bin || {
		err "PostgreSQL binaries not found. Install PostgreSQL ${PG_VERSION} for your user, set --pg-bin-dir/PG_BIN_DIR, or add postgres/initdb/pg_ctl/psql to PATH."
		return 2
	}
}

_user_pg_bin() {
	local name="${1:?binary}" bin_dir
	bin_dir="$(_user_pg_bin_dir)" || return $?
	printf '%s/%s\n' "$bin_dir" "$name"
}

_user_binary_major() {
	local bin="${1:?binary}" output token
	output=$("$bin" --version 2>/dev/null || true)
	for token in $output; do
		if [[ "$token" =~ ^[0-9]+([.][0-9]+)? ]]; then
			printf '%s\n' "${token%%.*}"
			return 0
		fi
	done
	return 1
}

_user_pgdata_empty() {
	local data_dir="${1:?data_dir}"
	[[ ! -e "$data_dir" ]] && return 0
	[[ -d "$data_dir" ]] || return 1
	local -a entries relevant=()
	shopt -s nullglob dotglob
	entries=("$data_dir"/*)
	shopt -u nullglob dotglob
	local entry base
	for entry in "${entries[@]}"; do
		base="$(basename -- "$entry")"
		case "$base" in
		server.crt | server.key) ;;
		*) relevant+=("$entry") ;;
		esac
	done
	((${#relevant[@]} == 0))
}

_user_valid_pgdata() {
	! _user_pgdata_problem "${1:?data_dir}" >/dev/null
}

_user_pgdata_problem() {
	local data_dir="${1:?data_dir}" on_disk_ver owner_uid current_uid mode mode_num
	[[ -d "$data_dir" ]] || {
		printf 'PGDATA directory is missing: %s\n' "$data_dir"
		return 0
	}
	owner_uid=$(stat -c '%u' -- "$data_dir" 2>/dev/null || true)
	current_uid=$(id -u)
	if [[ -z "$owner_uid" || "$owner_uid" != "$current_uid" ]]; then
		printf 'PGDATA owner uid %s does not match current uid %s\n' "${owner_uid:-unknown}" "$current_uid"
		return 0
	fi
	mode=$(stat -c '%a' -- "$data_dir" 2>/dev/null || true)
	if [[ -z "$mode" ]]; then
		printf 'Could not stat PGDATA mode: %s\n' "$data_dir"
		return 0
	fi
	mode_num=$((8#$mode))
	if ((mode_num & 0027)); then
		printf 'PGDATA mode %s is too open; expected 0700 or 0750-compatible owner-private layout\n' "$mode"
		return 0
	fi
	[[ -f "$data_dir/PG_VERSION" ]] || {
		printf 'PG_VERSION is missing\n'
		return 0
	}
	on_disk_ver=$(tr -d '[:space:]' <"$data_dir/PG_VERSION" 2>/dev/null || true)
	[[ "$on_disk_ver" == "$PG_VERSION" ]] || {
		printf 'PG_VERSION mismatch: found %s, expected %s\n' "${on_disk_ver:-unknown}" "$PG_VERSION"
		return 0
	}
	[[ -d "$data_dir/global" && -f "$data_dir/global/pg_control" ]] || {
		printf 'global/pg_control is missing\n'
		return 0
	}
	[[ -d "$data_dir/base" ]] || {
		printf 'base directory is missing\n'
		return 0
	}
	[[ -d "$data_dir/pg_wal" || -L "$data_dir/pg_wal" || -d "$data_dir/pg_xlog" || -L "$data_dir/pg_xlog" ]] || {
		printf 'WAL directory is missing (expected pg_wal or pg_xlog)\n'
		return 0
	}
	return 1
}

_user_print_pgdata_repair() {
	local data_dir="${1:?data_dir}" user group
	user=$(id -un 2>/dev/null || printf '<user>')
	group=$(id -gn 2>/dev/null || printf '<group>')
	err "Repair options:"
	err "  chown -R ${user}:${group} -- '${data_dir}' && chmod 0700 -- '${data_dir}'"
	err "  or choose an empty --data-dir/--user-base-dir; pgprovision will never delete this path."
}

_user_ensure_layout_dirs() {
	local base runtime log_file
	base="$(_user_base_dir)"
	runtime="$(_user_runtime_dir)"
	log_file="$(_user_log_file)"
	install -d -m 0700 -- "$base" "$runtime" "$(dirname -- "$log_file")"
}

_user_extension_control_file() {
	runtime_extension_control_file "${1:?control}"
}

_user_require_extension_control() {
	local label="${1:?label}" control="${2:?control}" control_file
	control_file="$(_user_extension_control_file "$control" 2>/dev/null || printf '<unknown>/extension/%s.control\n' "$control")"
	if [[ -r "$control_file" ]]; then
		return 0
	fi
	err "User-mode ${label} requested but extension control file is missing: ${control_file}"
	err "Install matching ${label} extension files for PostgreSQL ${PG_VERSION}; user mode does not install packages."
	exit 2
}

os_prepare_repos() {
	local repo_kind="${1:-${REPO_KIND:-none}}"
	case "$repo_kind" in
	none | "") return 0 ;;
	pgdg | os)
		err "User mode uses preinstalled PostgreSQL binaries and cannot prepare --repo ${repo_kind}; use --repo none or omit --repo."
		exit 2
		;;
	*)
		err "Unsupported user-mode repo '${repo_kind}'; use --repo none."
		exit 2
		;;
	esac
}

os_install_packages() {
	local bin_dir name major
	local -a missing=()
	bin_dir="$(_user_pg_bin_dir)" || exit $?
	for name in postgres initdb pg_ctl psql; do
		if [[ ! -x "${bin_dir}/${name}" ]]; then
			missing+=("${bin_dir}/${name}")
		fi
	done
	if ((${#missing[@]} > 0)); then
		err "Required PostgreSQL ${PG_VERSION} binaries are missing or not executable: ${missing[*]}"
		err "Set --pg-bin-dir/PG_BIN_DIR to a directory containing postgres, initdb, pg_ctl, and psql."
		exit 2
	fi
	for name in postgres initdb pg_ctl psql; do
		major="$(_user_binary_major "${bin_dir}/${name}")" || {
			err "Could not determine ${name} version from ${bin_dir}/${name} --version"
			exit 2
		}
		if [[ "$major" != "$PG_VERSION" ]]; then
			err "Expected ${name} PostgreSQL ${PG_VERSION}.x, found major ${major} at ${bin_dir}/${name}"
			exit 2
		fi
	done
	# shellcheck disable=SC2034 # consumed by provision.sh after this sourced backend returns
	PG_BIN_DIR="$bin_dir"
}

os_install_extension_packages() {
	if [[ "${INIT_PG_STAT_STATEMENTS:-false}" == "true" ]]; then
		_user_require_extension_control "pg_stat_statements" "pg_stat_statements"
	fi
	if [[ "${INIT_PGVECTOR:-false}" == "true" ]]; then
		_user_require_extension_control "pgvector" "vector"
	fi
}

os_self_heal() {
	local data_dir problem
	data_dir="$(_user_data_dir)"
	if _user_pgdata_empty "$data_dir"; then
		return 0
	fi
	if ! problem=$(_user_pgdata_problem "$data_dir"); then
		return 0
	fi
	err "Invalid user-mode PGDATA at ${data_dir}; pgprovision will not delete or repair it automatically."
	err "Detected: ${problem}"
	_user_print_pgdata_repair "$data_dir"
	exit 2
}

os_init_cluster() {
	local requested="${1:-${DATA_DIR:-auto}}" data_dir initdb_bin
	if [[ -n "$requested" && "$requested" != "auto" ]]; then
		DATA_DIR="$requested"
	fi
	data_dir="$(_user_data_dir)"
	DATA_DIR="$data_dir"
	_user_ensure_layout_dirs
	install -d -m 0700 -- "$data_dir"

	if _user_pgdata_empty "$data_dir"; then
		local crt_tmp="" key_tmp="" tmp_dir=""
		if [[ "${ENABLE_TLS:-false}" == "true" ]]; then
			validate_tls_prereqs
		fi
		tmp_dir="$(mktemp -d)"
		chmod 0700 "$tmp_dir"
		if [[ -f "$data_dir/server.crt" ]]; then
			crt_tmp="${tmp_dir}/server.crt"
			mv -- "$data_dir/server.crt" "$crt_tmp"
		fi
		if [[ -f "$data_dir/server.key" ]]; then
			key_tmp="${tmp_dir}/server.key"
			mv -- "$data_dir/server.key" "$key_tmp"
		fi
		initdb_bin="$(_user_pg_bin initdb)" || exit $?
		if run "$initdb_bin" -D "$data_dir"; then
			:
		else
			local rc=$?
			[[ -n "$crt_tmp" ]] && mv -f -- "$crt_tmp" "$data_dir/server.crt"
			[[ -n "$key_tmp" ]] && mv -f -- "$key_tmp" "$data_dir/server.key"
			rmdir "$tmp_dir" 2>/dev/null || true
			err "initdb ${data_dir} (rc=$rc)"
			exit "$rc"
		fi
		if [[ -n "$crt_tmp" ]]; then
			mv -f -- "$crt_tmp" "$data_dir/server.crt"
		fi
		if [[ -n "$key_tmp" ]]; then
			mv -f -- "$key_tmp" "$data_dir/server.key"
		fi
		rmdir "$tmp_dir" 2>/dev/null || true
	fi
	if ! _user_valid_pgdata "$data_dir"; then
		local problem
		problem=$(_user_pgdata_problem "$data_dir" || true)
		err "Invalid user-mode PGDATA at ${data_dir} after init check."
		err "Detected: ${problem:-unknown validation failure}"
		_user_print_pgdata_repair "$data_dir"
		exit 2
	fi
}

os_get_paths() {
	local data_dir base runtime log_file socket_dir service
	data_dir="$(_user_data_dir)"
	DATA_DIR="$data_dir"
	base="$(_user_base_dir)"
	runtime="$(_user_runtime_dir)"
	log_file="$(_user_log_file)"
	socket_dir="${UNIX_SOCKET_DIR:-$runtime}"
	service="user:${data_dir}"
	install -d -m 0700 -- "$base" "$runtime" "$socket_dir" "$(dirname -- "$log_file")"
	printf 'CONF_FILE=%q HBA_FILE=%q IDENT_FILE=%q DATA_DIR=%q SERVICE=%q PGPROVISION_USER_BASE_DIR=%q PGPROVISION_USER_RUNTIME_DIR=%q UNIX_SOCKET_DIR=%q LOG_FILE=%q\n' \
		"${data_dir}/postgresql.conf" \
		"${data_dir}/pg_hba.conf" \
		"${data_dir}/pg_ident.conf" \
		"$data_dir" \
		"$service" \
		"$base" \
		"$runtime" \
		"$socket_dir" \
		"$log_file"
}

os_restart() {
	local data_dir="${DATA_DIR:-}" log_file pg_ctl_bin
	[[ -z "$data_dir" || "$data_dir" == "auto" ]] && data_dir="$(_user_data_dir)"
	DATA_DIR="$data_dir"
	log_file="${LOG_FILE:-$(_user_log_file)}"
	_user_ensure_layout_dirs
	pg_ctl_bin="$(_user_pg_bin pg_ctl)" || exit $?
	if "$pg_ctl_bin" -D "$data_dir" status >/dev/null 2>&1; then
		must_run "restart user-mode PostgreSQL at ${data_dir}" "$pg_ctl_bin" -D "$data_dir" -l "$log_file" restart
	else
		must_run "start user-mode PostgreSQL at ${data_dir}" "$pg_ctl_bin" -D "$data_dir" -l "$log_file" start
	fi
}

os_stop_cluster() {
	local data_dir="${DATA_DIR:-}" pg_ctl_bin
	[[ -z "$data_dir" || "$data_dir" == "auto" ]] && data_dir="$(_user_data_dir)"
	pg_ctl_bin="$(_user_pg_bin pg_ctl)" || exit $?
	if [[ ! -x "$pg_ctl_bin" ]]; then
		err "pg_ctl is not executable: ${pg_ctl_bin}"
		return 1
	fi
	local status_rc=0
	"$pg_ctl_bin" -D "$data_dir" status >/dev/null 2>&1 || status_rc=$?
	case "$status_rc" in
	0)
		run "$pg_ctl_bin" -D "$data_dir" stop -m fast
		;;
	3)
		return 0
		;;
	4)
		if [[ ! -d "$data_dir" || ! -r "$data_dir" || ! -x "$data_dir" ]]; then
			warn "User-mode PostgreSQL data directory ${data_dir} is missing or inaccessible; treating cluster as already stopped."
			return 0
		fi
		err "Unable to determine user-mode PostgreSQL status at ${data_dir} with ${pg_ctl_bin} (rc=${status_rc})"
		return "$status_rc"
		;;
	*)
		err "Unable to determine user-mode PostgreSQL status at ${data_dir} with ${pg_ctl_bin} (rc=${status_rc})"
		return "$status_rc"
		;;
	esac
}

os_stop() {
	os_stop_cluster "$@"
}

_user_realpath() {
	realpath -m -- "${1:?path}"
}

_user_path_under_base() {
	local path="${1:?path}" base path_real base_real
	base="$(_user_base_dir)"
	path_real="$(_user_realpath "$path")" || return $?
	base_real="$(_user_realpath "$base")" || return $?
	[[ "$path_real" == "$base_real" || "$path_real" == "$base_real"/* ]]
}

_user_owned_path_if_exists() {
	local path="${1:?path}" owner_uid current_uid
	[[ -e "$path" ]] || return 0
	owner_uid=$(stat -c '%u' -- "$path" 2>/dev/null || true)
	current_uid=$(id -u)
	[[ -n "$owner_uid" && "$owner_uid" == "$current_uid" ]] || {
		err "Refusing to remove path not owned by current user: ${path}"
		return 1
	}
}

_user_confirm_covers_pgdata() {
	local expected="uninstall:${PG_VERSION}:user:${DATA_DIR:?}"
	[[ "${UNINSTALL_CONFIRM_TOKEN:-}" == "$expected" && "${PGPROVISION_CONFIRM_UNINSTALL:-}" == "$expected" ]]
}

_user_pgdata_removal_allowed() {
	_user_owned_path_if_exists "${DATA_DIR:?}" || return $?
	if _user_path_under_base "$DATA_DIR"; then
		return 0
	fi
	if _user_confirm_covers_pgdata; then
		warn "Removing user-mode PGDATA outside PGPROVISION_USER_BASE_DIR because the confirmation token explicitly covers ${DATA_DIR}."
		return 0
	fi
	err "Refusing to remove user-mode PGDATA outside PGPROVISION_USER_BASE_DIR without an exact uninstall confirmation token: ${DATA_DIR}"
	return 1
}

_user_path_overlaps_pgdata() {
	local path="${1:?path}" path_real data_real
	path_real="$(_user_realpath "$path")" || return $?
	data_real="$(_user_realpath "${DATA_DIR:?}")" || return $?
	[[ "$path_real" == "$data_real" || "$path_real" == "$data_real"/* || "$data_real" == "$path_real"/* ]]
}

_user_remove_file_if_exists() {
	local path="${1:?path}"
	[[ -e "$path" ]] || return 0
	_user_owned_path_if_exists "$path" || return $?
	run rm -f -- "$path" || return $?
}

_user_remove_tree_if_exists() {
	local path="${1:?path}"
	[[ -e "$path" ]] || return 0
	_user_owned_path_if_exists "$path" || return $?
	case "$(_user_realpath "$path")" in
	"/" | "${HOME}" | "${HOME}/")
		err "Refusing unsafe user-mode removal path: ${path}"
		return 1
		;;
	esac
	run rm -rf -- "$path" || return $?
}

os_uninstall_cluster() {
	local data_dir="${DATA_DIR:-}" runtime_dir log_file
	[[ -z "$data_dir" || "$data_dir" == "auto" ]] && data_dir="$(_user_data_dir)"
	DATA_DIR="$data_dir"
	runtime_dir="${UNIX_SOCKET_DIR:-$(_user_runtime_dir)}"
	log_file="${LOG_FILE:-$(_user_log_file)}"

	if [[ "${REMOVE_PGDATA:-false}" == "true" ]]; then
		_user_pgdata_removal_allowed || return $?
	fi

	_user_remove_file_if_exists "${DATA_DIR}/.pgprovision_provisioned.json" || return $?
	if _user_path_overlaps_pgdata "$log_file"; then
		warn "Skipping log cleanup because it overlaps preserved PGDATA: ${log_file}"
	else
		_user_remove_file_if_exists "$log_file" || return $?
	fi
	if _user_path_overlaps_pgdata "$runtime_dir"; then
		warn "Skipping runtime directory cleanup because it overlaps PGDATA: ${runtime_dir}"
	elif _user_path_under_base "$runtime_dir"; then
		_user_remove_tree_if_exists "$runtime_dir" || return $?
	elif [[ "$(_user_realpath "$runtime_dir")" == *"/pgprovision/pg${PG_VERSION}"* ]]; then
		_user_remove_tree_if_exists "$runtime_dir" || return $?
	else
		warn "Skipping runtime directory outside pgprovision-managed paths: ${runtime_dir}"
	fi

	if [[ "${REMOVE_PGDATA:-false}" == "true" ]]; then
		_user_remove_tree_if_exists "$DATA_DIR" || return $?
	fi
}

os_purge_packages() {
	local cache_root cache_version_dir
	cache_root="$(bootstrap_default_dir)"
	cache_version_dir="${cache_root}/${PG_VERSION}"
	if [[ -e "$cache_version_dir" ]]; then
		if ! _user_path_under_base "$cache_version_dir" && [[ -z "${PGPROVISION_BOOTSTRAP_DIR:-}" ]]; then
			err "Refusing to purge bootstrap cache outside user base: ${cache_version_dir}"
			return 1
		fi
		_user_remove_tree_if_exists "$cache_version_dir" || return $?
	fi
}

os_cleanup_repo() {
	log "User mode has no system PGDG repository cleanup; skipping."
}
