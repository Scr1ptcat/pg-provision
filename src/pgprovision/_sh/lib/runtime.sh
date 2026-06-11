# lib/runtime.sh
# shellcheck shell=bash
[[ ${__RUNTIME_LIB_LOADED:-0} -eq 1 ]] && return 0
__RUNTIME_LIB_LOADED=1

: "${RUNTIME_MODE:=system}"
: "${RUNTIME_DRY_RUN:=${DRY_RUN:-false}}"
declare -a RUNTIME_MANIFEST_ACTIONS=()
declare -a RUNTIME_MANIFEST_DETAILS=()

runtime_manifest_add() {
	local action="${1:?action}" detail="${2:-}"
	RUNTIME_MANIFEST_ACTIONS+=("$action")
	RUNTIME_MANIFEST_DETAILS+=("$detail")
}

runtime_manifest_print() {
	local i
	((${#RUNTIME_MANIFEST_ACTIONS[@]} == 0)) && return 0
	printf '  runtime_manifest:\n'
	for i in "${!RUNTIME_MANIFEST_ACTIONS[@]}"; do
		printf '    - action: %s\n' "${RUNTIME_MANIFEST_ACTIONS[$i]}"
		printf '      detail: %s\n' "${RUNTIME_MANIFEST_DETAILS[$i]}"
	done
}

runtime_is_dry_run() {
	[[ "${RUNTIME_DRY_RUN:-${DRY_RUN:-false}}" == "true" || "${DRY_RUN:-false}" == "true" ]]
}

runtime_user_base_dir() {
	if [[ -n "${PGPROVISION_USER_BASE_DIR:-}" ]]; then
		printf '%s\n' "$PGPROVISION_USER_BASE_DIR"
	elif [[ -n "${XDG_DATA_HOME:-}" ]]; then
		printf '%s\n' "${XDG_DATA_HOME}/pgprovision/pg${PG_VERSION:-16}"
	else
		printf '%s\n' "${HOME}/.local/share/pgprovision/pg${PG_VERSION:-16}"
	fi
}

runtime_user_runtime_dir() {
	if [[ -n "${PGPROVISION_USER_RUNTIME_DIR:-}" ]]; then
		printf '%s\n' "$PGPROVISION_USER_RUNTIME_DIR"
	elif [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
		printf '%s\n' "${XDG_RUNTIME_DIR}/pgprovision/pg${PG_VERSION:-16}"
	else
		printf '%s\n' "$(runtime_user_base_dir)/run"
	fi
}

runtime_require_system_elevation() {
	runtime_is_dry_run && return 0
	if [[ $(id -u) -eq 0 ]]; then return 0; fi
	if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then return 0; fi
	err "This script needs root or passwordless sudo (sudo -n)."
	exit 1
}

runtime_init() {
	local mode="${1:-system}" dry_run="${2:-false}"
	RUNTIME_MODE="$mode"
	RUNTIME_DRY_RUN="$dry_run"
	DRY_RUN="$dry_run"
	RUNTIME_MANIFEST_ACTIONS=()
	RUNTIME_MANIFEST_DETAILS=()
	SUDO=()

	if [[ "$mode" != "system" && "$mode" != "user" ]]; then
		err "Unsupported runtime mode: $mode"
		exit 2
	fi

	if [[ "$mode" == "user" && "$dry_run" != "true" && $(id -u) -eq 0 ]]; then
		err "User mode must be run as the target non-root OS user, not root."
		exit 2
	fi

	if [[ "$mode" == "system" && "$dry_run" != "true" ]]; then
		runtime_require_system_elevation
		if [[ $(id -u) -ne 0 ]]; then SUDO=(sudo -n); fi
	fi
}

runtime_elevate() {
	if runtime_is_dry_run; then
		runtime_manifest_add "exec" "$*"
		return 0
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		run "$@"
		return $?
	fi
	if [[ $(id -u) -eq 0 ]]; then
		run "$@"
	else
		run sudo -n "$@"
	fi
}

runtime_as_postgres() {
	if runtime_is_dry_run; then
		runtime_manifest_add "postgres" "$*"
		return 0
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		run_quiet "$@"
		return $?
	fi
	local -a sudo_cmd=(sudo)
	if [[ "$(declare -p SUDO 2>/dev/null || true)" == declare\ -a* ]] && ((${#SUDO[@]} > 0)); then
		sudo_cmd=("${SUDO[@]}")
	fi
	run_quiet "${sudo_cmd[@]}" -u postgres "$@"
}

runtime_psql() {
	local db="${1:-postgres}"
	shift || true
	local -a host_args=()
	local socket_dir="${UNIX_SOCKET_DIR:-}"
	if [[ -z "$socket_dir" && "${RUNTIME_MODE:-system}" == "user" ]]; then
		socket_dir="$(runtime_user_runtime_dir)"
	fi
	if [[ -n "$socket_dir" ]]; then
		host_args=(-h "$socket_dir")
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		local psql_cmd="psql" bin_dir=""
		if bin_dir=$(runtime_resolve_pg_bin 2>/dev/null); then
			[[ -x "${bin_dir}/psql" ]] && psql_cmd="${bin_dir}/psql"
		fi
		runtime_as_postgres "$psql_cmd" -v ON_ERROR_STOP=1 -XAt "${host_args[@]}" -p "${PORT:-5432}" -U "$(id -un)" -d "$db" "$@"
		return $?
	fi
	runtime_as_postgres psql -v ON_ERROR_STOP=1 -XAt "${host_args[@]}" -p "${PORT:-5432}" -d "$db" "$@"
}

runtime_write_file_atomic() {
	local target="${1:?target}" mode="${2:-}" owner="${3:-}" group="${4:-}"
	if runtime_is_dry_run; then
		cat >/dev/null
		runtime_manifest_add "write_file" "$target mode=${mode:-preserve} owner=${owner:-preserve} group=${group:-preserve}"
		return 0
	fi

	local dir base staging rc
	dir="$(dirname -- "$target")"
	base="$(basename -- "$target")"
	staging="${dir}/.${base}.pgprovision.$$"

	if [[ -f "$target" ]]; then
		if [[ -z "$mode" ]]; then
			mode=$(stat -c '%a' -- "$target") || {
				err "cannot stat mode of $target"
				return 1
			}
		fi
		if [[ -z "$owner" ]]; then
			owner=$(stat -c '%U' -- "$target") || {
				err "cannot stat owner of $target"
				return 1
			}
			[[ "$owner" == "UNKNOWN" ]] && owner=$(stat -c '%u' -- "$target")
		fi
		if [[ -z "$group" ]]; then
			group=$(stat -c '%G' -- "$target") || {
				err "cannot stat group of $target"
				return 1
			}
			[[ "$group" == "UNKNOWN" ]] && group=$(stat -c '%g' -- "$target")
		fi
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		owner=""
		group=""
	fi

	runtime_elevate tee "$staging" >/dev/null || return $?
	if [[ -n "$owner" && -n "$group" ]]; then
		runtime_elevate chown "$owner:$group" "$staging" || {
			rc=$?
			runtime_elevate rm -f -- "$staging" || true
			return "$rc"
		}
	elif [[ -n "$owner" ]]; then
		runtime_elevate chown "$owner" "$staging" || {
			rc=$?
			runtime_elevate rm -f -- "$staging" || true
			return "$rc"
		}
	elif [[ -n "$group" ]]; then
		runtime_elevate chgrp "$group" "$staging" || {
			rc=$?
			runtime_elevate rm -f -- "$staging" || true
			return "$rc"
		}
	fi
	if [[ -n "$mode" ]]; then
		runtime_elevate chmod "$mode" "$staging" || {
			rc=$?
			runtime_elevate rm -f -- "$staging" || true
			return "$rc"
		}
	fi
	runtime_elevate mv -f -- "$staging" "$target" || {
		rc=$?
		runtime_elevate rm -f -- "$staging" || true
		return "$rc"
	}
}

runtime_chown_like() {
	local ref="${1:?ref}" target="${2:?target}"
	if runtime_is_dry_run; then
		runtime_manifest_add "chown_like" "$target like $ref"
		return 0
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		return 0
	fi
	runtime_elevate chown --reference "$ref" "$target"
}

runtime_resolve_pg_bin() {
	if [[ -n "${PG_BIN_DIR:-}" ]]; then
		printf '%s\n' "$PG_BIN_DIR"
		return 0
	fi
	local dir
	for dir in "/usr/lib/postgresql/${PG_VERSION:-16}/bin" "/usr/pgsql-${PG_VERSION:-16}/bin"; do
		if [[ -x "$dir/psql" || -x "$dir/postgres" ]]; then
			printf '%s\n' "$dir"
			return 0
		fi
	done
	local psql_path postgres_path
	postgres_path=$(command -v postgres 2>/dev/null || true)
	if [[ -n "$postgres_path" ]]; then
		dir="$(dirname -- "$postgres_path")"
		printf '%s\n' "$dir"
		return 0
	fi
	psql_path=$(command -v psql 2>/dev/null || true)
	if [[ -n "$psql_path" ]]; then
		dir="$(dirname -- "$psql_path")"
		printf '%s\n' "$dir"
		return 0
	fi
	return 1
}

runtime_pg_share_candidates() {
	local bin_dir share
	if bin_dir=$(runtime_resolve_pg_bin 2>/dev/null); then
		if [[ -x "${bin_dir}/pg_config" ]]; then
			share=$("${bin_dir}/pg_config" --sharedir 2>/dev/null || true)
			[[ -n "$share" ]] && printf '%s\n' "$share"
		fi
		share="$(cd "${bin_dir}/.." 2>/dev/null && pwd)/share"
		[[ "$share" != "/share" ]] && printf '%s\n' "$share"
	fi
	printf '%s\n' "/usr/share/postgresql/${PG_VERSION:-16}"
	printf '%s\n' "/usr/pgsql-${PG_VERSION:-16}/share"
}

runtime_resolve_pg_share() {
	if [[ -n "${PG_SHARE_DIR:-}" ]]; then
		printf '%s\n' "$PG_SHARE_DIR"
		return 0
	fi
	local share seen=":"
	while IFS= read -r share; do
		[[ -z "$share" ]] && continue
		[[ "$seen" == *":$share:"* ]] && continue
		seen="${seen}${share}:"
		if [[ -d "${share}/extension" ]]; then
			printf '%s\n' "$share"
			return 0
		fi
	done < <(runtime_pg_share_candidates)
	return 1
}

runtime_extension_control_file() {
	local control="${1:?control}" share fallback
	if share=$(runtime_resolve_pg_share); then
		printf '%s/extension/%s.control\n' "$share" "$control"
		return 0
	fi
	fallback=$(runtime_pg_share_candidates | sed -n '1p')
	[[ -n "$fallback" ]] || fallback="<unknown>"
	printf '%s/extension/%s.control\n' "$fallback" "$control"
	return 1
}
