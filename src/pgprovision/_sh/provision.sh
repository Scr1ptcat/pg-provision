#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PGPROVISION_DEFAULT_PG_VERSION="${PGPROVISION_DEFAULT_PG_VERSION:-18}"
export PGPROVISION_DEFAULT_PG_VERSION

# shellcheck source=src/pgprovision/_sh/lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

# shellcheck source=src/pgprovision/_sh/lib/runtime.sh
. "${SCRIPT_DIR}/lib/runtime.sh"

# shellcheck source=src/pgprovision/_sh/lib/bootstrap.sh
. "${SCRIPT_DIR}/lib/bootstrap.sh"

# shellcheck source=src/pgprovision/_sh/lib/hba.sh
. "${SCRIPT_DIR}/lib/hba.sh"

# shellcheck source=src/pgprovision/_sh/lib/profile.sh
. "${SCRIPT_DIR}/lib/profile.sh"

require_root_or_sudo() {
	runtime_require_system_elevation
}

readonly -a RHEL_IDS=(rhel rocky almalinux centos ol oraclelinux amzn fedora redhat)
readonly -a DEB_IDS=(ubuntu debian linuxmint pop neon zorin raspbian kali elementary)

# Match any whole-word token in $1 against the remaining args.
# Uses the " space $hay space " trick for word boundaries; RHEL7-safe (no declare -n).
has_any_token() {
	local hay=" $1 " t
	shift
	for t in "$@"; do
		[[ "$hay" == *" $t "* ]] && return 0
	done
	return 1
}

os_detect() {
	local osrel="${OS_RELEASE_PATH:-/etc/os-release}"
	[[ -r "$osrel" ]] || {
		err "$osrel not found"
		exit 2
	}
	# shellcheck disable=SC1090,SC1091
	. "$osrel"

	# shellcheck disable=SC2034
	OS_VERSION_ID="${VERSION_ID:-}"
	# shellcheck disable=SC2034
	OS_CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"

	local tokens="${ID:-} ${ID_LIKE:-}"
	if has_any_token "$tokens" "${RHEL_IDS[@]}"; then
		OS_FAMILY="rhel"
	elif has_any_token "$tokens" "${DEB_IDS[@]}"; then
		OS_FAMILY="ubuntu"
	else
		err "Unsupported OS: ID=${ID:-unknown} ID_LIKE=${ID_LIKE:-}"
		exit 2
	fi
}

load_os_module() {
	local file="${SCRIPT_DIR}/os/${OS_FAMILY}.sh"
	[[ -r "$file" ]] || {
		err "Missing module: $file"
		exit 2
	}

	# shellcheck source=src/pgprovision/_sh/os/rhel.sh
	# shellcheck source=src/pgprovision/_sh/os/ubuntu.sh
	# shellcheck source=src/pgprovision/_sh/os/user.sh
	# shellcheck disable=SC1091
	. "$file"

	local req=(
		os_prepare_repos
		os_install_packages
		os_install_extension_packages
		os_init_cluster
		os_get_paths
		os_restart
		os_self_heal
		os_stop_cluster
		os_uninstall_cluster
		os_purge_packages
		os_cleanup_repo
	)
	local missing=() fn
	for fn in "${req[@]}"; do declare -F "$fn" >/dev/null || missing+=("$fn"); done
	((${#missing[@]} == 0)) || {
		err "OS module '$OS_FAMILY' missing: ${missing[*]}"
		exit 2
	}
}

ensure_conf_dir_like_conf() {
	local conf_file="$1"
	local dropin_dir
	dropin_dir="$(dirname -- "$conf_file")/conf.d"

	# Already present → nothing to do
	[[ -d "$dropin_dir" ]] && return 0
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		must_run "create user-owned drop-in dir: $dropin_dir" \
			runtime_elevate install -d -m 0700 -- "$dropin_dir"
		return 0
	fi

	local owner="" group=""

	# Try to match base config ownership if it exists
	if [[ -f "$conf_file" ]]; then
		owner=$(stat -c '%U' -- "$conf_file" 2>/dev/null) || owner=""
		group=$(stat -c '%G' -- "$conf_file" 2>/dev/null) || group=""
		[[ "$owner" == "UNKNOWN" ]] && owner=$(stat -c '%u' -- "$conf_file" 2>/dev/null || echo "")
		[[ "$group" == "UNKNOWN" ]] && group=$(stat -c '%g' -- "$conf_file" 2>/dev/null || echo "")
	else
		# Optional nicety: if postgres exists, mirror that user for the new dir
		if id -u postgres >/dev/null 2>&1; then
			owner="postgres"
			group="postgres"
		fi
	fi

	if [[ -n "$owner" && -n "$group" ]]; then
		must_run "create drop-in dir with owner/group ($owner:$group): $dropin_dir" \
			runtime_elevate install -d -o "$owner" -g "$group" -m 0700 -- "$dropin_dir"
	else
		must_run "create drop-in dir: $dropin_dir" \
			runtime_elevate install -d -m 0700 -- "$dropin_dir"
	fi
}

# Default config (can be overridden via flags or env file)
[[ -n "${REPO_KIND+x}" ]] && REPO_KIND_EXPLICIT=true || REPO_KIND_EXPLICIT=false
[[ -n "${UNIX_SOCKET_GROUP+x}" ]] && UNIX_SOCKET_GROUP_EXPLICIT=true || UNIX_SOCKET_GROUP_EXPLICIT=false
[[ -n "${UNIX_SOCKET_PERMISSIONS+x}" ]] && UNIX_SOCKET_PERMISSIONS_EXPLICIT=true || UNIX_SOCKET_PERMISSIONS_EXPLICIT=false
[[ -n "${ADMIN_GROUP_ROLE+x}" ]] && ADMIN_GROUP_ROLE_EXPLICIT=true || ADMIN_GROUP_ROLE_EXPLICIT=false
PGPROVISION_MODE=${PGPROVISION_MODE:-}
USER_MODE=${USER_MODE:-false}
PG_BIN_DIR=${PG_BIN_DIR:-}
PGPROVISION_USER_BASE_DIR=${PGPROVISION_USER_BASE_DIR:-}
PGPROVISION_USER_RUNTIME_DIR=${PGPROVISION_USER_RUNTIME_DIR:-}
PGPROVISION_BOOTSTRAP_TARBALL=${PGPROVISION_BOOTSTRAP_TARBALL:-}
PGPROVISION_BOOTSTRAP_SHA256=${PGPROVISION_BOOTSTRAP_SHA256:-}
PGPROVISION_BOOTSTRAP_DIR=${PGPROVISION_BOOTSTRAP_DIR:-}
BOOTSTRAP_ONLY=${BOOTSTRAP_ONLY:-false}
PG_VERSION=${PG_VERSION:-$PGPROVISION_DEFAULT_PG_VERSION}
REPO_KIND=${REPO_KIND:-} # system default pgdg; user-mode default none
PORT=${PORT:-5432}
LISTEN_ADDRESSES=${LISTEN_ADDRESSES:-localhost}
ALLOWED_CIDR=${ALLOWED_CIDR:-}
ALLOWED_CIDR_V6=${ALLOWED_CIDR_V6:-}
DATA_DIR=${DATA_DIR:-auto}
ENABLE_TLS=${ENABLE_TLS:-false}
CREATE_DB=${CREATE_DB:-}
CREATE_USER=${CREATE_USER:-}
CREATE_PASSWORD=${CREATE_PASSWORD:-}
ALLOW_NETWORK=${ALLOW_NETWORK:-false}
PROFILE=${PROFILE:-}
ENV_FILE=${ENV_FILE:-}
DRY_RUN=${DRY_RUN:-false}
DESTROY_DB=${DESTROY_DB:-}
DESTROY_USER=${DESTROY_USER:-}
DESTROY_ONLY=${DESTROY_ONLY:-false}
PGPROVISION_CONFIRM_DESTROY_DB=${PGPROVISION_CONFIRM_DESTROY_DB:-}
UNINSTALL_CLUSTER=${UNINSTALL_CLUSTER:-false}
UNINSTALL_ONLY=${UNINSTALL_ONLY:-false}
PGPROVISION_CONFIRM_UNINSTALL=${PGPROVISION_CONFIRM_UNINSTALL:-}
REMOVE_PGDATA=${REMOVE_PGDATA:-false}
PURGE_PACKAGES=${PURGE_PACKAGES:-false}
REMOVE_PGDG_REPO=${REMOVE_PGDG_REPO:-false}
INIT_PG_STAT_STATEMENTS=${INIT_PG_STAT_STATEMENTS:-false}
INIT_PGVECTOR=${INIT_PGVECTOR:-false}
PGVECTOR_DB=${PGVECTOR_DB:-}
PGVECTOR_PACKAGE=${PGVECTOR_PACKAGE:-}
SELF_HEAL=${SELF_HEAL:-true}

# Local hardening flags
SOCKET_ONLY=${SOCKET_ONLY:-}
UNIX_SOCKET_GROUP=${UNIX_SOCKET_GROUP-pgclients}
UNIX_SOCKET_PERMISSIONS=${UNIX_SOCKET_PERMISSIONS-0770}
UNIX_SOCKET_DIR=${UNIX_SOCKET_DIR:-}
LOCAL_PEER_MAP=${LOCAL_PEER_MAP:-localmap}
ADMIN_GROUP_ROLE=${ADMIN_GROUP_ROLE-dba_group}
ADMIN_DBROLE=${ADMIN_DBROLE:-}
DISABLE_POSTGRES_LOGIN=${DISABLE_POSTGRES_LOGIN:-false}
declare -a LOCAL_MAP_ENTRIES=()

usage() {
	cat <<USAGE
Postgres Provisioner
Usage: $0 \
  [--user-mode] [--pg-bin-dir DIR] [--user-base-dir DIR] [--user-runtime-dir DIR] \\
  [--bootstrap-tarball PATH_OR_URL] [--bootstrap-sha256 HASH] [--bootstrap-dir DIR] [--bootstrap-only] \\
  [--pg-version N] [--repo pgdg|os|none] [--port N] [--listen-addresses VAL] [--allowed-cidr CIDR] [--allowed-cidr-v6 CIDR6] \\
  [--data-dir PATH|auto] [--enable-tls] [--init-pg-stat-statements] [--init-pgvector] [--pgvector-db NAME] \\
  [--no-self-heal] \\
  [--create-db NAME] [--create-user NAME] [--create-password SECRET] [--allow-network] [--profile NAME] [--env-file FILE] [--dry-run] \\
  [--destroy-db NAME] [--destroy-user ROLE] [--destroy-only] [--confirm-destroy-db NAME] \\
  [--uninstall-cluster] [--uninstall-only] [--confirm-uninstall TOKEN] [--remove-pgdata] [--purge-packages] [--remove-pgdg-repo] \\
  [--socket-only] [--unix-socket-group NAME] [--unix-socket-permissions MODE] [--unix-socket-dir PATH] \\
  [--local-peer-map NAME] [--local-map-entry OSUSER:DBROLE]... [--admin-group-role NAME] [--admin-dbrole NAME] [--disable-postgres-login]

Examples:
  sudo $0 --repo pgdg --listen-addresses '*' --allowed-cidr 10.0.0.0/8 --allow-network
  $0 --user-mode --pg-bin-dir /path/to/postgres/bin --user-base-dir ~/.local/share/pgprovision/pg18
  $0 --user-mode --bootstrap-tarball ./postgresql.tar.gz --bootstrap-sha256 <sha256> --bootstrap-only
  sudo $0 --destroy-db old_app --destroy-user old_app --confirm-destroy-db old_app --destroy-only
  $0 --uninstall-cluster --uninstall-only --dry-run
  sudo $0 --uninstall-cluster --uninstall-only --confirm-uninstall uninstall:18:ubuntu:/var/lib/postgresql/18/main
USAGE
}

parse_args() {
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--user-mode)
			PGPROVISION_MODE=user
			USER_MODE=true
			shift 1
			;;
		--pg-bin-dir)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--pg-bin-dir requires a directory"
				exit 2
			fi
			PG_BIN_DIR="$2"
			shift 2
			;;
		--user-base-dir)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--user-base-dir requires a directory"
				exit 2
			fi
			PGPROVISION_USER_BASE_DIR="$2"
			shift 2
			;;
		--user-runtime-dir)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--user-runtime-dir requires a directory"
				exit 2
			fi
			PGPROVISION_USER_RUNTIME_DIR="$2"
			shift 2
			;;
		--bootstrap-tarball)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--bootstrap-tarball requires a path or URL"
				exit 2
			fi
			PGPROVISION_BOOTSTRAP_TARBALL="$2"
			shift 2
			;;
		--bootstrap-sha256)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--bootstrap-sha256 requires a SHA256 digest"
				exit 2
			fi
			PGPROVISION_BOOTSTRAP_SHA256="$2"
			shift 2
			;;
		--bootstrap-dir)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--bootstrap-dir requires a directory"
				exit 2
			fi
			PGPROVISION_BOOTSTRAP_DIR="$2"
			shift 2
			;;
		--bootstrap-only)
			BOOTSTRAP_ONLY=true
			shift 1
			;;
		--pg-version)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--pg-version requires a numeric PostgreSQL major version value"
				exit 2
			fi
			if [[ ! "$2" =~ ^[0-9]+$ ]]; then
				err "--pg-version must be a numeric PostgreSQL major version, got: $2"
				exit 2
			fi
			PG_VERSION="$2"
			shift 2
			;;
		--repo)
			REPO_KIND_EXPLICIT=true
			REPO_KIND="$2"
			shift 2
			;;
		--port)
			PORT="$2"
			shift 2
			;;
		--listen-addresses)
			LISTEN_ADDRESSES="$2"
			shift 2
			;;
		--allowed-cidr)
			ALLOWED_CIDR="$2"
			shift 2
			;;
		--allowed-cidr-v6)
			ALLOWED_CIDR_V6="$2"
			shift 2
			;;
		--data-dir)
			DATA_DIR="$2"
			shift 2
			;;
		--enable-tls)
			ENABLE_TLS=true
			shift 1
			;;
		--init-pg-stat-statements)
			INIT_PG_STAT_STATEMENTS=true
			shift 1
			;;
		--init-pgvector)
			INIT_PGVECTOR=true
			shift 1
			;;
		--pgvector-db)
			PGVECTOR_DB="$2"
			shift 2
			;;
		--pgvector-package)
			PGVECTOR_PACKAGE="$2"
			shift 2
			;;
		--no-self-heal)
			SELF_HEAL=false
			shift 1
			;;
		--create-db)
			CREATE_DB="$2"
			shift 2
			;;
		--create-user)
			CREATE_USER="$2"
			shift 2
			;;
		--create-password)
			CREATE_PASSWORD="$2"
			shift 2
			;;
		--allow-network)
			ALLOW_NETWORK=true
			shift 1
			;;
		--profile)
			PROFILE="$2"
			shift 2
			;;
		--env-file)
			ENV_FILE="$2"
			shift 2
			;;
		--socket-only)
			SOCKET_ONLY=true
			shift 1
			;;
		--unix-socket-group)
			UNIX_SOCKET_GROUP_EXPLICIT=true
			UNIX_SOCKET_GROUP="$2"
			shift 2
			;;
		--unix-socket-permissions)
			UNIX_SOCKET_PERMISSIONS_EXPLICIT=true
			UNIX_SOCKET_PERMISSIONS="$2"
			shift 2
			;;
		--unix-socket-dir)
			UNIX_SOCKET_DIR="$2"
			shift 2
			;;
		--local-peer-map)
			LOCAL_PEER_MAP="$2"
			shift 2
			;;
		--local-map-entry)
			LOCAL_MAP_ENTRIES+=("$2")
			shift 2
			;;
		--admin-group-role)
			ADMIN_GROUP_ROLE="$2"
			ADMIN_GROUP_ROLE_EXPLICIT=true
			shift 2
			;;
		--admin-dbrole)
			ADMIN_DBROLE="$2"
			shift 2
			;;
		--disable-postgres-login)
			DISABLE_POSTGRES_LOGIN=true
			shift 1
			;;
		--dry-run)
			DRY_RUN=true
			shift 1
			;;
		--destroy-db)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--destroy-db requires a database name"
				exit 2
			fi
			DESTROY_DB="$2"
			shift 2
			;;
		--destroy-user)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--destroy-user requires a role name"
				exit 2
			fi
			DESTROY_USER="$2"
			shift 2
			;;
		--destroy-only)
			DESTROY_ONLY=true
			shift 1
			;;
		--confirm-destroy-db)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--confirm-destroy-db requires a database name"
				exit 2
			fi
			PGPROVISION_CONFIRM_DESTROY_DB="$2"
			shift 2
			;;
		--uninstall-cluster)
			UNINSTALL_CLUSTER=true
			shift 1
			;;
		--uninstall-only)
			UNINSTALL_ONLY=true
			shift 1
			;;
		--confirm-uninstall)
			if [[ $# -lt 2 || "$2" == --* ]]; then
				err "--confirm-uninstall requires a confirmation token"
				exit 2
			fi
			PGPROVISION_CONFIRM_UNINSTALL="$2"
			shift 2
			;;
		--remove-pgdata)
			REMOVE_PGDATA=true
			shift 1
			;;
		--purge-packages)
			PURGE_PACKAGES=true
			shift 1
			;;
		--remove-pgdg-repo)
			REMOVE_PGDG_REPO=true
			shift 1
			;;
		-h | --help)
			usage
			exit 0
			;;
		*)
			err "Unknown argument: $1"
			usage
			exit 2
			;;
		esac
	done
}

pgprovision_truthy() {
	local value="${1:-}"
	value="${value//[[:space:]]/}"
	case "${value,,}" in
	1 | true | yes | on) return 0 ;;
	*) return 1 ;;
	esac
}

pgprovision_normalize_bool() {
	local var="${1:?var}" value
	value="${!var:-false}"
	if pgprovision_truthy "$value"; then
		printf -v "$var" '%s' "true"
	else
		printf -v "$var" '%s' "false"
	fi
}

normalize_uninstall_flags() {
	pgprovision_normalize_bool REMOVE_PGDATA
	pgprovision_normalize_bool PURGE_PACKAGES
	pgprovision_normalize_bool REMOVE_PGDG_REPO
	pgprovision_normalize_bool UNINSTALL_CLUSTER
	pgprovision_normalize_bool UNINSTALL_ONLY
}

user_mode_requested() {
	[[ "${PGPROVISION_MODE,,}" == "user" ]] && return 0
	pgprovision_truthy "${USER_MODE:-false}"
}

env_file_assigns() {
	local var="${1:?var}"
	[[ -n "${ENV_FILE:-}" && -r "${ENV_FILE:-}" ]] || return 1
	grep -Eq "^[[:space:]]*(export[[:space:]]+)?${var}[[:space:]]*=" "${ENV_FILE}"
}

load_env_file() {
	if [[ -n "${ENV_FILE}" && -r "${ENV_FILE}" ]]; then
		log "Loading env file: ${ENV_FILE}"
		env_file_assigns REPO_KIND && REPO_KIND_EXPLICIT=true
		env_file_assigns UNIX_SOCKET_GROUP && UNIX_SOCKET_GROUP_EXPLICIT=true
		env_file_assigns UNIX_SOCKET_PERMISSIONS && UNIX_SOCKET_PERMISSIONS_EXPLICIT=true
		env_file_assigns ADMIN_GROUP_ROLE && ADMIN_GROUP_ROLE_EXPLICIT=true
		set -a # export
		# shellcheck disable=SC1090
		. "${ENV_FILE}"
		set +a
	fi
}

resolve_mode_defaults() {
	if user_mode_requested; then
		PGPROVISION_MODE=user
		USER_MODE=true
		RUNTIME_REQUESTED_MODE=user
		if [[ "${REPO_KIND_EXPLICIT:-false}" != "true" || -z "${REPO_KIND:-}" ]]; then
			REPO_KIND=none
		fi
		if [[ "${UNIX_SOCKET_GROUP_EXPLICIT:-false}" != "true" ]]; then
			UNIX_SOCKET_GROUP=""
		fi
		if [[ "${UNIX_SOCKET_PERMISSIONS_EXPLICIT:-false}" != "true" ]]; then
			if [[ -n "${UNIX_SOCKET_GROUP:-}" ]]; then
				UNIX_SOCKET_PERMISSIONS=0770
			else
				UNIX_SOCKET_PERMISSIONS=0700
			fi
		fi
		if [[ "${ADMIN_GROUP_ROLE_EXPLICIT:-false}" != "true" ]]; then
			ADMIN_GROUP_ROLE=""
		fi
		if [[ "${SOCKET_ONLY:-false}" == "true" ]]; then
			LISTEN_ADDRESSES=""
		fi
	else
		RUNTIME_REQUESTED_MODE=system
		[[ -z "${REPO_KIND:-}" ]] && REPO_KIND=pgdg
	fi
}

destroy_requested() {
	[[ -n "${DESTROY_DB:-}${DESTROY_USER:-}" || "${DESTROY_ONLY:-false}" == "true" ]]
}

uninstall_requested() {
	pgprovision_truthy "${UNINSTALL_CLUSTER:-false}" ||
		pgprovision_truthy "${UNINSTALL_ONLY:-false}" ||
		[[ -n "${PGPROVISION_CONFIRM_UNINSTALL:-}" ]] ||
		pgprovision_truthy "${REMOVE_PGDATA:-false}" ||
		pgprovision_truthy "${PURGE_PACKAGES:-false}" ||
		pgprovision_truthy "${REMOVE_PGDG_REPO:-false}"
}

_uninstall_expected_token() {
	if [[ -z "${OS_FAMILY:-}" || -z "${DATA_DIR:-}" || "${DATA_DIR:-auto}" == "auto" ]]; then
		err "Internal error: uninstall target must be resolved before computing confirmation token"
		return 2
	fi
	printf 'uninstall:%s:%s:%s\n' "${PG_VERSION}" "${OS_FAMILY}" "${DATA_DIR}"
}

_uninstall_stamp_roots() {
	case "${OS_FAMILY:-}" in
	user)
		printf '%s\n' "$(runtime_user_base_dir)/data"
		;;
	ubuntu)
		printf '/var/lib/postgresql/%s/main\n' "${PG_VERSION}"
		;;
	rhel)
		printf '/var/lib/pgsql/%s/data\n' "${PG_VERSION}"
		printf '/var/lib/pgsql/data\n'
		;;
	esac
}

_uninstall_add_candidate() {
	local path="${1:-}" source="${2:-unknown}" i
	[[ -n "$path" && "$path" != "auto" ]] || return 0
	for i in "${!UNINSTALL_CANDIDATE_PATHS[@]}"; do
		if [[ "${UNINSTALL_CANDIDATE_PATHS[i]}" == "$path" ]]; then
			UNINSTALL_CANDIDATE_SOURCES[i]="${UNINSTALL_CANDIDATE_SOURCES[i]},${source}"
			return 0
		fi
	done
	UNINSTALL_CANDIDATE_PATHS+=("$path")
	UNINSTALL_CANDIDATE_SOURCES+=("$source")
}

resolve_uninstall_target() {
	local requested="${DATA_DIR:-auto}" datadir root count i
	UNINSTALL_TARGET_SOURCE=""
	UNINSTALL_CANDIDATE_PATHS=()
	UNINSTALL_CANDIDATE_SOURCES=()

	if [[ -n "$requested" && "$requested" != "auto" ]]; then
		DATA_DIR="$requested"
		UNINSTALL_TARGET_SOURCE="explicit-data-dir"
		return 0
	fi

	if [[ "${OS_FAMILY:-}" == "ubuntu" ]] && command -v pg_lsclusters >/dev/null 2>&1; then
		while IFS= read -r datadir; do
			_uninstall_add_candidate "$datadir" "pg_lsclusters:${PG_VERSION}/main"
		done < <(pg_lsclusters --no-header 2>/dev/null | awk -v v="$PG_VERSION" '$1==v && $2=="main"{print $6}')
	fi

	while IFS= read -r root; do
		[[ -n "$root" ]] || continue
		if [[ -r "${root}/.pgprovision_provisioned.json" ]]; then
			_uninstall_add_candidate "$root" "stamp:${root}/.pgprovision_provisioned.json"
		fi
	done < <(_uninstall_stamp_roots)

	count=${#UNINSTALL_CANDIDATE_PATHS[@]}
	if ((count == 0)); then
		err "Could not resolve uninstall target for PostgreSQL ${PG_VERSION} on ${OS_FAMILY:-unknown}."
		err "Pass an explicit --data-dir or ensure the pgprovision stamp is readable."
		exit 2
	fi
	if ((count > 1)); then
		err "Multiple uninstall targets resolved; pass explicit --data-dir."
		for i in "${!UNINSTALL_CANDIDATE_PATHS[@]}"; do
			err "  ${UNINSTALL_CANDIDATE_PATHS[$i]} (${UNINSTALL_CANDIDATE_SOURCES[$i]})"
		done
		exit 2
	fi

	DATA_DIR="${UNINSTALL_CANDIDATE_PATHS[0]}"
	UNINSTALL_TARGET_SOURCE="${UNINSTALL_CANDIDATE_SOURCES[0]}"
}

validate_uninstall_request() {
	local expected provided
	if ! pgprovision_truthy "${UNINSTALL_CLUSTER:-false}"; then
		err "--uninstall-cluster is required for uninstall flags"
		exit 2
	fi
	if pgprovision_truthy "${REMOVE_PGDG_REPO:-false}" && [[ "${RUNTIME_REQUESTED_MODE:-system}" == "user" ]]; then
		err "--remove-pgdg-repo is system-mode only"
		exit 2
	fi
	if pgprovision_truthy "${REMOVE_PGDG_REPO:-false}" && ! pgprovision_truthy "${PURGE_PACKAGES:-false}"; then
		err "--remove-pgdg-repo requires --purge-packages"
		exit 2
	fi

	expected="$(_uninstall_expected_token)" || exit $?
	UNINSTALL_CONFIRM_TOKEN="$expected"
	if [[ "${DRY_RUN:-false}" == "true" ]]; then
		return 0
	fi

	if ! pgprovision_truthy "${UNINSTALL_ONLY:-false}"; then
		err "Non-dry-run cluster uninstall requires --uninstall-only."
		err "Refusing to combine uninstall and provision in one invocation."
		exit 2
	fi

	provided="${PGPROVISION_CONFIRM_UNINSTALL:-}"
	if [[ "$provided" != "$expected" ]]; then
		err "Uninstall confirmation mismatch"
		err "Expected confirmation: ${expected}"
		err "Provided confirmation: ${provided:-<empty>}"
		exit 2
	fi
}

_uninstall_service_name() {
	case "${OS_FAMILY:-}" in
	ubuntu) printf 'postgresql@%s-main\n' "${PG_VERSION}" ;;
	rhel)
		if declare -F _rhel_service_name >/dev/null; then
			_rhel_service_name
		else
			printf 'postgresql-%s\n' "${PG_VERSION}"
		fi
		;;
	user) printf 'user:%s\n' "${DATA_DIR}" ;;
	*) printf '<unknown>\n' ;;
	esac
}

build_uninstall_manifest() {
	UNINSTALL_CONFIRM_TOKEN="$(_uninstall_expected_token)" || exit $?
	SERVICE="$(_uninstall_service_name)"
	case "${OS_FAMILY:-}" in
	ubuntu)
		CONF_FILE="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
		HBA_FILE="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"
		IDENT_FILE="/etc/postgresql/${PG_VERSION}/main/pg_ident.conf"
		UNINSTALL_CONFIG_DIR="/etc/postgresql/${PG_VERSION}/main"
		UNINSTALL_PACKAGE_PATTERNS=("postgresql-${PG_VERSION}" "postgresql-client-${PG_VERSION}" "postgresql-${PG_VERSION}-pgvector")
		UNINSTALL_REPO_CLEANUP_PATHS=("/etc/apt/sources.list.d/pgdg.list" "/etc/apt/keyrings/postgresql.gpg")
		;;
	rhel)
		CONF_FILE="${DATA_DIR}/postgresql.conf"
		HBA_FILE="${DATA_DIR}/pg_hba.conf"
		IDENT_FILE="${DATA_DIR}/pg_ident.conf"
		UNINSTALL_CONFIG_DIR="${DATA_DIR}"
		UNINSTALL_PACKAGE_PATTERNS=("postgresql${PG_VERSION}*" "pgvector_${PG_VERSION}")
		UNINSTALL_REPO_CLEANUP_PATHS=("/etc/yum.repos.d/pgdg-redhat-all.repo" "/etc/yum.repos.d/pgdg-redhat.repo")
		;;
	user)
		CONF_FILE="${DATA_DIR}/postgresql.conf"
		HBA_FILE="${DATA_DIR}/pg_hba.conf"
		IDENT_FILE="${DATA_DIR}/pg_ident.conf"
		UNINSTALL_CONFIG_DIR="${DATA_DIR}"
		UNINSTALL_PACKAGE_PATTERNS=("bootstrap-cache:${PGPROVISION_BOOTSTRAP_DIR:-$(bootstrap_default_dir)}/${PG_VERSION}")
		UNINSTALL_REPO_CLEANUP_PATHS=()
		;;
	*)
		CONF_FILE=""
		HBA_FILE=""
		IDENT_FILE=""
		UNINSTALL_CONFIG_DIR=""
		UNINSTALL_PACKAGE_PATTERNS=()
		UNINSTALL_REPO_CLEANUP_PATHS=()
		;;
	esac

	runtime_manifest_add "uninstall.stop_cluster" "${SERVICE}"
	runtime_manifest_add "uninstall.cluster_metadata" "${OS_FAMILY}:${PG_VERSION}/main config=${UNINSTALL_CONFIG_DIR:-<none>}"
	if pgprovision_truthy "${REMOVE_PGDATA:-false}"; then
		runtime_manifest_add "uninstall.remove_pgdata" "${DATA_DIR}"
	else
		runtime_manifest_add "uninstall.preserve_pgdata" "${DATA_DIR}"
	fi
	if pgprovision_truthy "${PURGE_PACKAGES:-false}"; then
		runtime_manifest_add "uninstall.purge_packages" "${UNINSTALL_PACKAGE_PATTERNS[*]:-<none>}"
	fi
	if pgprovision_truthy "${REMOVE_PGDG_REPO:-false}"; then
		runtime_manifest_add "uninstall.cleanup_repo" "${UNINSTALL_REPO_CLEANUP_PATHS[*]:-<none>}"
	fi
}

print_uninstall_manifest() {
	local item
	log "Cluster uninstall manifest:"
	printf '  mode: %s\n' "${RUNTIME_REQUESTED_MODE:-system}"
	printf '  os_family: %s\n' "${OS_FAMILY:-unknown}"
	printf '  pg_version: %s\n' "${PG_VERSION}"
	printf '  target_source: %s\n' "${UNINSTALL_TARGET_SOURCE:-<unknown>}"
	printf '  service: %s\n' "${SERVICE:-$(_uninstall_service_name)}"
	printf '  config_dir: %s\n' "${UNINSTALL_CONFIG_DIR:-<none>}"
	printf '  conf_file: %s\n' "${CONF_FILE:-<none>}"
	printf '  hba_file: %s\n' "${HBA_FILE:-<none>}"
	printf '  ident_file: %s\n' "${IDENT_FILE:-<none>}"
	printf '  data_dir: %s\n' "${DATA_DIR}"
	printf '  remove_pgdata: %s\n' "${REMOVE_PGDATA:-false}"
	printf '  purge_packages: %s\n' "${PURGE_PACKAGES:-false}"
	if pgprovision_truthy "${PURGE_PACKAGES:-false}"; then
		printf '  package_patterns:\n'
		for item in "${UNINSTALL_PACKAGE_PATTERNS[@]}"; do
			printf '    - %s\n' "$item"
		done
	fi
	printf '  remove_pgdg_repo: %s\n' "${REMOVE_PGDG_REPO:-false}"
	if pgprovision_truthy "${REMOVE_PGDG_REPO:-false}"; then
		printf '  repo_cleanup_paths:\n'
		for item in "${UNINSTALL_REPO_CLEANUP_PATHS[@]}"; do
			printf '    - %s\n' "$item"
		done
	fi
	printf 'confirm_token=%s\n' "${UNINSTALL_CONFIRM_TOKEN:-$(_uninstall_expected_token)}"
	runtime_manifest_print
}

_uninstall_print_step_list() {
	local title="${1:?title}" body="${2:-}" line printed=false
	err "$title"
	while IFS= read -r line; do
		[[ -n "$line" ]] || continue
		err "  - $line"
		printed=true
	done <<<"$body"
	[[ "$printed" == "true" ]] || err "  - <none>"
}

_uninstall_step_enabled() {
	case "${1:?step}" in
	stop_cluster | uninstall_cluster) return 0 ;;
	purge_packages) pgprovision_truthy "${PURGE_PACKAGES:-false}" ;;
	cleanup_repo) pgprovision_truthy "${REMOVE_PGDG_REPO:-false}" ;;
	*) return 1 ;;
	esac
}

_uninstall_step_list_contains() {
	local body="${1:-}" needle="${2:?needle}" line
	while IFS= read -r line; do
		[[ "$line" == "$needle" ]] && return 0
	done <<<"$body"
	return 1
}

_uninstall_append_step_once() {
	local body="${1:-}" step="${2:?step}"
	if _uninstall_step_list_contains "$body" "$step"; then
		printf '%s' "$body"
	elif [[ -n "$body" ]]; then
		printf '%s\n%s\n' "$body" "$step"
	else
		printf '%s\n' "$step"
	fi
}

_uninstall_skipped_steps_for_failure() {
	local failed_step="${1:?failed_step}" skipped="${2:-}" step after_failed=false
	for step in stop_cluster uninstall_cluster purge_packages cleanup_repo; do
		if [[ "$step" == "$failed_step" ]]; then
			after_failed=true
			continue
		fi
		if [[ "$after_failed" == "true" ]] || ! _uninstall_step_enabled "$step"; then
			skipped="$(_uninstall_append_step_once "$skipped" "$step")"
		fi
	done
	printf '%s' "$skipped"
}

_uninstall_print_recovery_commands() {
	local failed_step="${1:-unknown}" svc="${SERVICE:-$(_uninstall_service_name)}"
	err "Manual recovery commands for failed step '${failed_step}':"
	case "${OS_FAMILY:-}" in
	ubuntu)
		err "  pg_lsclusters --no-header"
		err "  systemctl status ${svc}"
		if [[ -n "${UNINSTALL_QUARANTINE_PATH:-}" ]]; then
			err "  sudo mv -T -- '${UNINSTALL_QUARANTINE_PATH}' '/etc/postgresql/${PG_VERSION}/main'"
		fi
		err "  sudo $0 --uninstall-cluster --uninstall-only --remove-pgdata --confirm-uninstall '${UNINSTALL_CONFIRM_TOKEN:-$(_uninstall_expected_token)}'"
		;;
	rhel)
		err "  systemctl status ${svc}"
		err "  sudo systemctl daemon-reload"
		err "  sudo $0 --uninstall-cluster --uninstall-only --remove-pgdata --confirm-uninstall '${UNINSTALL_CONFIRM_TOKEN:-$(_uninstall_expected_token)}'"
		;;
	user)
		err "  pg_ctl -D '${DATA_DIR}' status"
		err "  $0 --user-mode --uninstall-cluster --uninstall-only --remove-pgdata --confirm-uninstall '${UNINSTALL_CONFIRM_TOKEN:-$(_uninstall_expected_token)}'"
		;;
	*)
		err "  Re-run dry-run to inspect the manifest and token."
		;;
	esac
}

_uninstall_report_failure() {
	local failed_step="${1:?failed_step}" rc="${2:?rc}" completed="${3:-}" skipped="${4:-}"
	skipped="$(_uninstall_skipped_steps_for_failure "$failed_step" "$skipped")"
	err "Cluster uninstall failed at step '${failed_step}' (rc=${rc})."
	_uninstall_print_step_list "Completed uninstall steps:" "$completed"
	_uninstall_print_step_list "Skipped uninstall steps:" "$skipped"
	_uninstall_print_recovery_commands "$failed_step"
}

execute_uninstall_manifest() {
	local completed="" skipped="" rc=0

	if os_stop_cluster; then
		completed+="stop_cluster"$'\n'
	else
		rc=$?
		_uninstall_report_failure "stop_cluster" "$rc" "$completed" "$skipped"
		return "$rc"
	fi

	if os_uninstall_cluster; then
		completed+="uninstall_cluster"$'\n'
	else
		rc=$?
		_uninstall_report_failure "uninstall_cluster" "$rc" "$completed" "$skipped"
		return "$rc"
	fi

	if pgprovision_truthy "${PURGE_PACKAGES:-false}"; then
		if os_purge_packages; then
			completed+="purge_packages"$'\n'
		else
			rc=$?
			_uninstall_report_failure "purge_packages" "$rc" "$completed" "$skipped"
			return "$rc"
		fi
	else
		skipped+="purge_packages"$'\n'
	fi

	if pgprovision_truthy "${REMOVE_PGDG_REPO:-false}"; then
		if os_cleanup_repo; then
			completed+="cleanup_repo"$'\n'
		else
			rc=$?
			_uninstall_report_failure "cleanup_repo" "$rc" "$completed" "$skipped"
			return "$rc"
		fi
	else
		skipped+="cleanup_repo"$'\n'
	fi

	log "Cluster uninstall completed."
}

validate_user_mode_mvp_limits() {
	[[ "${RUNTIME_REQUESTED_MODE:-system}" == "user" ]] || return 0
	case "${REPO_KIND:-none}" in
	none | "") ;;
	*)
		err "User mode uses preinstalled PostgreSQL binaries and cannot prepare --repo ${REPO_KIND}; use --repo none or omit --repo."
		exit 2
		;;
	esac
	if [[ -n "${ADMIN_DBROLE:-}" && -z "${ADMIN_GROUP_ROLE:-}" ]]; then
		err "User-mode --admin-dbrole requires an explicit --admin-group-role."
		exit 2
	fi
}

pg_sql_identifier_escape() {
	printf '%s' "${1-}" | sed 's/"/""/g'
}

pg_sql_literal_escape() {
	printf '%s' "${1-}" | sed "s/'/''/g"
}

validate_destroy_name() {
	local kind="$1" value="$2"
	local byte_len
	if [[ -z "$value" ]]; then
		err "Destroy ${kind} name must not be empty"
		exit 2
	fi
	if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
		err "Destroy ${kind} name must not contain newlines"
		exit 2
	fi
	if [[ "$value" == *"*"* || "$value" == *"?"* || "$value" == *"["* || "$value" == *"]"* ]]; then
		err "Destroy ${kind} name must not contain wildcard characters"
		exit 2
	fi
	byte_len=$(printf '%s' "$value" | wc -c | tr -d '[:space:]')
	if ((byte_len > 63)); then
		err "Destroy ${kind} name must be at most 63 bytes to avoid PostgreSQL identifier truncation"
		exit 2
	fi
}

validate_destroy_request() {
	if [[ -z "${DESTROY_DB:-}" ]]; then
		err "--destroy-db is required for logical destroy"
		exit 2
	fi

	validate_destroy_name "database" "$DESTROY_DB"
	local db_lower="${DESTROY_DB,,}"
	case "$db_lower" in
	postgres | template0 | template1 | pg_*)
		err "Refusing to destroy protected database: ${DESTROY_DB}"
		exit 2
		;;
	esac

	if [[ -n "${DESTROY_USER:-}" ]]; then
		validate_destroy_name "role" "$DESTROY_USER"
		local role_lower="${DESTROY_USER,,}"
		case "$role_lower" in
		postgres | pg_*)
			err "Refusing to destroy protected role: ${DESTROY_USER}"
			exit 2
			;;
		esac
		if [[ -n "${ADMIN_DBROLE:-}" && "$DESTROY_USER" == "$ADMIN_DBROLE" ]]; then
			err "Refusing to destroy configured admin DB role: ${DESTROY_USER}"
			exit 2
		fi
		if [[ -n "${ADMIN_GROUP_ROLE:-}" && "$DESTROY_USER" == "$ADMIN_GROUP_ROLE" ]]; then
			err "Refusing to destroy configured admin group role: ${DESTROY_USER}"
			exit 2
		fi
	fi

	if [[ "${DRY_RUN:-false}" != "true" && "${PGPROVISION_CONFIRM_DESTROY_DB:-}" != "$DESTROY_DB" ]]; then
		err "Destroy confirmation mismatch"
		err "Expected confirmation: ${DESTROY_DB}"
		err "Provided confirmation: ${PGPROVISION_CONFIRM_DESTROY_DB:-<empty>}"
		exit 2
	fi
}

print_destroy_manifest() {
	local continue_provision=true
	[[ "${DESTROY_ONLY:-false}" == "true" ]] && continue_provision=false
	log "Logical destroy manifest:"
	printf '  destroy_db: %s\n' "${DESTROY_DB}"
	printf '  destroy_user: %s\n' "${DESTROY_USER:-<none>}"
	printf '  connect_db: postgres\n'
	printf '  continue_provision: %s\n' "$continue_provision"
	printf '  dry_run: %s\n' "${DRY_RUN:-false}"
}

print_provision_dry_run_manifest() {
	log "Provision dry-run manifest:"
	printf '  pg_version: %s\n' "${PG_VERSION}"
	printf '  os_family: %s\n' "${OS_FAMILY:-unknown}"
	printf '  repo: %s\n' "${REPO_KIND}"
	printf '  data_dir: %s\n' "${DATA_DIR}"
	printf '  create_db: %s\n' "${CREATE_DB:-<none>}"
	printf '  create_user: %s\n' "${CREATE_USER:-<none>}"
	printf '  init_pg_stat_statements: %s\n' "${INIT_PG_STAT_STATEMENTS}"
	printf '  init_pgvector: %s\n' "${INIT_PGVECTOR}"
	runtime_manifest_print
	log "Dry-run: would prepare repos, install packages, initialize/start service, and configure PostgreSQL."
}

provision_psql() {
	runtime_psql "$@"
}

destroy_db_and_user() {
	local probe_output current_user current_user_err sql rc=0

	if ! probe_output=$(provision_psql postgres -c "SELECT 1;" 2>&1 >/dev/null); then
		if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
			err "PostgreSQL is not reachable for logical destroy (target: database=postgres via user-mode runtime psql)."
			err "Check service status with: pg_ctl -D '${DATA_DIR:-<user PGDATA>}' status"
		else
			err "PostgreSQL is not reachable for logical destroy (target: database=postgres via sudo -u postgres psql)."
			err "Check service status with: systemctl status postgresql; pg_ctlcluster ${PG_VERSION} main status; or user-mode pg_ctl status."
		fi
		if [[ -n "$probe_output" ]]; then
			err "psql detail: ${probe_output}"
		fi
		return 1
	fi

	if [[ -n "${DESTROY_USER:-}" ]]; then
		current_user_err="$(mktemp)"
		if ! current_user=$(provision_psql postgres -c "SELECT current_user;" 2>"$current_user_err"); then
			err "Could not resolve SQL current_user before dropping role ${DESTROY_USER}"
			if [[ -s "$current_user_err" ]]; then
				err "psql detail: $(<"$current_user_err")"
			fi
			rm -f "$current_user_err"
			return 1
		fi
		rm -f "$current_user_err"
		current_user=$(printf '%s\n' "$current_user" | sed -n '1p')
		if [[ "$DESTROY_USER" == "$current_user" ]]; then
			err "Refusing to destroy current SQL user: ${DESTROY_USER}"
			return 2
		fi
	fi

	sql=$(
		local _db_ident _db_lit
		_db_ident=$(pg_sql_identifier_escape "$DESTROY_DB")
		_db_lit=$(pg_sql_literal_escape "$DESTROY_DB")
		printf '%s\n' "SELECT pg_terminate_backend(pid)"
		printf '%s\n' "FROM pg_stat_activity"
		printf '%s\n' "WHERE datname = '${_db_lit}'"
		printf '%s\n' "  AND pid <> pg_backend_pid();"
		printf '%s\n' "DROP DATABASE IF EXISTS \"${_db_ident}\";"
		if [[ -n "${DESTROY_USER:-}" ]]; then
			local _role_ident
			_role_ident=$(pg_sql_identifier_escape "$DESTROY_USER")
			printf '%s\n' "DROP ROLE IF EXISTS \"${_role_ident}\";"
		fi
	)

	printf '%s\n' "$sql" | provision_psql postgres || rc=$?
	if ((rc != 0)); then
		err "Logical destroy failed while dropping database/role (rc=${rc})"
	fi
	return "$rc"
}

assert_psql_major_matches() {
	local bin_dir psql_bin psql_version_output ver
	if ! bin_dir=$(runtime_resolve_pg_bin); then
		err "psql not found after installation; expected PostgreSQL ${PG_VERSION} client"
		exit 2
	fi
	psql_bin="${bin_dir}/psql"
	if [[ ! -x "$psql_bin" ]]; then
		psql_bin=$(command -v psql 2>/dev/null || true)
	fi
	if [[ -z "$psql_bin" ]]; then
		err "psql not found after installation; expected PostgreSQL ${PG_VERSION} client"
		exit 2
	fi
	psql_version_output=$("$psql_bin" --version 2>/dev/null || true)
	ver=$(awk '{print $3}' <<<"$psql_version_output")
	if [[ -z "$ver" || "${ver%%.*}" != "${PG_VERSION}" ]]; then
		err "Expected PostgreSQL client ${PG_VERSION}.x, found: ${psql_version_output:-unknown}"
		exit 2
	fi
}

apply_dropin_config() {
	local conf_file="$1" data_dir="$2" dropin_dir dropin rendered effective_listen_addresses
	dropin_dir="$(dirname -- "$conf_file")/conf.d"
	dropin="${dropin_dir}/99-pgprovision.conf"
	effective_listen_addresses="$LISTEN_ADDRESSES"
	if [[ "${RUNTIME_MODE:-system}" == "user" && "${SOCKET_ONLY:-false}" == "true" ]]; then
		effective_listen_addresses=""
	fi

	ensure_conf_dir_like_conf "$conf_file"
	ensure_line "$conf_file" "include_dir = 'conf.d'"

	rendered=$(
		pg_escape() {
			local s=${1-} q="'"
			s=${s//"$q"/"$q$q"}
			printf '%s' "$s"
		}

		# Baseline settings
		printf 'port = %s\n' "$PORT"
		printf "listen_addresses = '%s'\n" "$(pg_escape "$effective_listen_addresses")"
		printf 'password_encryption = %s\n' 'scram-sha-256'
		local profile_has_spl=false profile_spl="" kv k v
		if [[ "$(declare -p PROFILE_OVERRIDES 2>/dev/null || true)" == declare\ -a* ]] &&
			((${#PROFILE_OVERRIDES[@]} > 0)); then
			for kv in "${PROFILE_OVERRIDES[@]}"; do
				k="${kv%%=*}"
				v="${kv#*=}"
				if [[ "$k" == "shared_preload_libraries" ]]; then
					profile_has_spl=true
					profile_spl="$v"
				fi
			done
		fi
		if [[ "$profile_has_spl" == "true" ]]; then
			if [[ "$INIT_PG_STAT_STATEMENTS" == "true" && "$profile_spl" != *pg_stat_statements* ]]; then
				local raw_spl="$profile_spl"
				if [[ "$raw_spl" == \'*\' && "$raw_spl" == *\' ]]; then
					raw_spl="${raw_spl:1:${#raw_spl}-2}"
				fi
				if [[ -n "$raw_spl" ]]; then
					printf "shared_preload_libraries = '%s,pg_stat_statements'\n" "$(pg_escape "$raw_spl")"
				else
					printf "shared_preload_libraries = '%s'\n" 'pg_stat_statements'
				fi
			else
				printf 'shared_preload_libraries = %s\n' "$profile_spl"
			fi
		elif [[ "$INIT_PG_STAT_STATEMENTS" == "true" ]]; then
			printf "shared_preload_libraries = '%s'\n" 'pg_stat_statements'
		fi
		printf 'logging_collector = %s\n' 'on'
		printf 'log_min_duration_statement = %s\n' '250ms'
		printf 'log_connections = %s\n' 'on'
		printf 'log_disconnections = %s\n' 'on'
		printf "log_line_prefix = '%s'\n" "$(pg_escape '%m [%p] user=%u db=%d app=%a client=%h ')"

		# Socket gating
		if [[ -n "${UNIX_SOCKET_GROUP:-}" ]]; then
			printf "unix_socket_group = '%s'\n" "$(pg_escape "$UNIX_SOCKET_GROUP")"
		fi
		printf 'unix_socket_permissions = %s\n' "$UNIX_SOCKET_PERMISSIONS"
		if [[ -n "${UNIX_SOCKET_DIR}" ]]; then
			printf "unix_socket_directories = '%s'\n" "$(pg_escape "$UNIX_SOCKET_DIR")"
		fi

		# TLS semantics (note: value with dot must be quoted)
		if [[ "$ENABLE_TLS" == "true" ]]; then
			printf 'ssl = %s\n' 'on'
			printf "ssl_min_protocol_version = '%s'\n" "$(pg_escape 'TLSv1.2')"
			printf 'ssl_prefer_server_ciphers = %s\n' 'on'
		else
			printf 'ssl = %s\n' 'off'
		fi

		# Optional profile overrides
		if [[ "$(declare -p PROFILE_OVERRIDES 2>/dev/null || true)" == declare\ -a* ]] &&
			((${#PROFILE_OVERRIDES[@]} > 0)); then
			for kv in "${PROFILE_OVERRIDES[@]}"; do
				k="${kv%%=*}"
				v="${kv#*=}"
				[[ "$k" =~ ^[[:alnum:]_.]+$ ]] || {
					warn "skip invalid key: $k"
					continue
				}
				[[ "$v" != *$'\n'* ]] || {
					warn "skip newline in value for $k"
					continue
				}
				[[ "$k" == "shared_preload_libraries" ]] && continue
				printf '%s = %s\n' "$k" "$v"
			done
		fi
	)

	printf '%s\n' "$rendered" | runtime_write_file_atomic "$dropin" "0600" "" ""
	runtime_chown_like "$conf_file" "$dropin"
	# Restore SELinux context if available (no-op elsewhere)
	if command -v restorecon >/dev/null 2>&1; then
		soft_run "restorecon context for $dropin" restorecon -q "$dropin"
	fi
}
replace_managed_block_top() {
	local file="$1"
	shift
	local begin_marker="$1"
	shift
	local end_marker="$1"
	shift
	local content="$1"
	shift
	# optional: reference file to copy attributes from when $file does not exist
	local ref="${1:-}" # may be empty
	# optional: default mode to apply when $file does not exist and ref not usable
	local default_mode="${2:-}" # e.g., "0600" for sensitive files; may be empty

	local mode="" owner="" group="" existing=""

	if [[ -f "$file" ]]; then
		# File exists: preserving attributes is required → failures are fatal
		mode=$(stat -c '%a' -- "$file") || {
			err "cannot stat mode of $file"
			return 1
		}
		owner=$(stat -c '%U' -- "$file") || {
			err "cannot stat owner of $file"
			return 1
		}
		group=$(stat -c '%G' -- "$file") || {
			err "cannot stat group of $file"
			return 1
		}
		[[ "$owner" == "UNKNOWN" ]] && owner=$(stat -c '%u' -- "$file") # fallback to numeric uid
		[[ "$group" == "UNKNOWN" ]] && group=$(stat -c '%g' -- "$file") # fallback to numeric gid
		existing=$(awk -v b="$begin_marker" -v e="$end_marker" '
      BEGIN {ib=0}
      $0==b {ib=1; next}
      ib==1 && $0==e {ib=0; next}
      ib==0 {print}
    ' "$file") || return 1
	else
		# Try to take attrs from ref if provided.
		if [[ -n "$ref" && -f "$ref" ]]; then
			owner=$(stat -c '%U' -- "$ref" 2>/dev/null || true)
			[[ "$owner" == "UNKNOWN" ]] && owner=$(stat -c '%u' -- "$ref" 2>/dev/null || true)
			group=$(stat -c '%G' -- "$ref" 2>/dev/null || true)
			[[ "$group" == "UNKNOWN" ]] && group=$(stat -c '%g' -- "$ref" 2>/dev/null || true)
		fi
		# Mode: use provided default if any (e.g., 0600 for HBA/ident). Leave empty otherwise.
		[[ -n "$default_mode" ]] && mode="$default_mode"
	fi

	{
		printf '%s\n' "$content"
		if [[ -n "$existing" ]]; then
			printf '%s\n' "$existing"
		fi
	} | runtime_write_file_atomic "$file" "$mode" "$owner" "$group"
}
write_pg_ident_map() {
	local ident_file="$1"
	local begin="# pgprovision:pg_ident begin (managed)"
	local end="# pgprovision:pg_ident end"
	local buf
	buf=$(printf '%s\n' "$begin" "# MAPNAME SYSTEM-USER DB-ROLE")
	if [[ "${RUNTIME_MODE:-system}" == "user" ]] && ((${#LOCAL_MAP_ENTRIES[@]} > 0)); then
		warn "User-mode pg_ident entries only map OS users that can already access the UNIX socket; pgprovision will not modify OS groups."
	fi
	local entry osuser dbrole
	for entry in "${LOCAL_MAP_ENTRIES[@]:-}"; do
		[[ -z "$entry" ]] && continue
		osuser="${entry%%:*}"
		dbrole="${entry#*:}"
		buf=$(printf '%s\n%s %s %s' "$buf" "$LOCAL_PEER_MAP" "$osuser" "$dbrole")
	done
	buf=$(printf '%s\n%s\n' "$buf" "$end")
	replace_managed_block_top "$ident_file" "$begin" "$end" "$buf" "${CONF_FILE:-}" "0600"
}

ensure_socket_group_and_members() {
	local group="$1"
	shift
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		[[ -z "$group" ]] && return 0
		if ! getent group "$group" >/dev/null; then
			err "User-mode socket group '${group}' does not exist; create it outside pgprovision or omit --unix-socket-group."
			exit 2
		fi
		local current_user groups
		current_user=$(id -un)
		groups=$(id -nG "$current_user" 2>/dev/null || id -nG)
		if [[ " ${groups} " != *" ${group} "* ]]; then
			err "User-mode socket group '${group}' exists, but ${current_user} is not a member."
			err "Ask an administrator to add ${current_user} to ${group}, then start a new login session."
			exit 2
		fi
		if [[ -n "${UNIX_SOCKET_DIR:-}" && -d "${UNIX_SOCKET_DIR}" ]]; then
			must_run "set socket dir group ${group}" runtime_elevate chgrp "$group" "$UNIX_SOCKET_DIR"
			must_run "set socket dir mode ${UNIX_SOCKET_PERMISSIONS}" runtime_elevate chmod "$UNIX_SOCKET_PERMISSIONS" "$UNIX_SOCKET_DIR"
		fi
		return 0
	fi
	# Ensure group exists
	if ! getent group "$group" >/dev/null; then
		must_run "create group $group" "${SUDO[@]}" groupadd -f "$group"
	fi
	# Ensure postgres belongs to the socket group
	if id -u postgres >/dev/null 2>&1; then
		must_run "add postgres to $group" "${SUDO[@]}" usermod -aG "$group" postgres
	fi
	# Add mapped OS users to the socket group
	local entry osuser
	for entry in "${LOCAL_MAP_ENTRIES[@]:-}"; do
		osuser="${entry%%:*}"
		if id -u "$osuser" >/dev/null 2>&1; then
			must_run "add $osuser to $group" "${SUDO[@]}" usermod -aG "$group" "$osuser"
		fi
	done
}

create_db_and_user() {
	[[ -z "$CREATE_DB$CREATE_USER" ]] && return 0
	local rc=0

	# Support secret from env var or file (file takes effect when var empty)
	local pw="${CREATE_PASSWORD:-}"
	if [[ -z "$pw" && -n "${CREATE_PASSWORD_FILE:-}" && -r "$CREATE_PASSWORD_FILE" ]]; then
		pw="$(<"$CREATE_PASSWORD_FILE")"
	fi

	# Build SQL in memory and pipe it to psql so secrets do not appear in argv.
	local sql
	sql=$(
		if [[ -n "$CREATE_USER" ]]; then
			local _user_ident _user_lit _role_sql _role_sql_lit
			_user_ident=$(printf '%s' "$CREATE_USER" | sed 's/"/""/g')
			_user_lit=$(printf '%s' "$CREATE_USER" | sed "s/'/''/g")
			_role_sql="CREATE ROLE \"${_user_ident}\" LOGIN"
			if [[ -n "$pw" ]]; then
				local _pass_lit
				_pass_lit=$(printf '%s' "$pw" | sed "s/'/''/g")
				_role_sql="${_role_sql} PASSWORD '${_pass_lit}'"
			fi
			_role_sql_lit=$(printf '%s' "$_role_sql" | sed "s/'/''/g")
			printf '%s\n' "SELECT '${_role_sql_lit}'"
			printf '%s\n' "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${_user_lit}')"
			printf '%s\n' "\\gexec"
		fi

		if [[ -n "$CREATE_DB" ]]; then
			local _db_ident _db_lit _create_db_sql _create_db_lit
			_db_ident=$(printf '%s' "$CREATE_DB" | sed 's/"/""/g')
			_db_lit=$(printf '%s' "$CREATE_DB" | sed "s/'/''/g")
			_create_db_sql="CREATE DATABASE \"${_db_ident}\""
			if [[ -n "$CREATE_USER" ]]; then
				local _owner_ident
				_owner_ident=$(printf '%s' "$CREATE_USER" | sed 's/"/""/g')
				_create_db_sql="${_create_db_sql} OWNER \"${_owner_ident}\""
			fi
			_create_db_lit=$(printf '%s' "$_create_db_sql" | sed "s/'/''/g")
			printf '%s\n' "SELECT '${_create_db_lit}'"
			printf '%s\n' "WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='${_db_lit}')"
			printf '%s\n' "\\gexec"
		fi
	)

	# Execute the SQL quietly; must not echo password-bearing lines.
	printf '%s\n' "$sql" | provision_psql postgres || rc=$?

	return "$rc"
}

conditionally_init_pg_stat_statements() {
	[[ "$INIT_PG_STAT_STATEMENTS" != "true" ]] && return 0
	# Create the extension if not present (requires shared_preload_libraries configured and server restarted)
	must_run "create pg_stat_statements extension" runtime_psql postgres -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
}

conditionally_init_pgvector() {
	[[ "$INIT_PGVECTOR" != "true" ]] && return 0
	local target_db="${PGVECTOR_DB:-${CREATE_DB:-postgres}}"
	must_run "create vector extension in ${target_db}" runtime_psql "$target_db" -c "CREATE EXTENSION IF NOT EXISTS vector;"
}

setup_role_mappings_and_admin() {
	# Create DB roles for mappings and optional admin group/login.
	local failed=false
	local entry dbrole dbrole_lit dbrole_ident
	for entry in "${LOCAL_MAP_ENTRIES[@]:-}"; do
		dbrole="${entry#*:}"
		[[ -z "$dbrole" ]] && continue
		dbrole_ident=$(printf '%s' "$dbrole" | sed 's/\"/\"\"/g')
		dbrole_lit=$(printf "%s" "$dbrole" | sed "s/'/''/g")
		if ! runtime_psql postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${dbrole_lit}') THEN CREATE ROLE \"${dbrole_ident}\" LOGIN; END IF; END \$\$;"; then
			warn "create role ${dbrole} failed"
			failed=true
		fi
	done
	if [[ -n "${ADMIN_GROUP_ROLE}" ]]; then
		local g_ident g_lit
		g_ident=$(printf '%s' "$ADMIN_GROUP_ROLE" | sed 's/\"/\"\"/g')
		g_lit=$(printf '%s' "$ADMIN_GROUP_ROLE" | sed "s/'/''/g")
		if ! runtime_psql postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${g_lit}') THEN CREATE ROLE \"${g_ident}\" SUPERUSER NOLOGIN; END IF; END \$\$;"; then
			warn "create group ${ADMIN_GROUP_ROLE} failed"
			failed=true
		fi
		if [[ -n "${ADMIN_DBROLE}" ]]; then
			local a_ident a_lit
			a_ident=$(printf '%s' "$ADMIN_DBROLE" | sed 's/\"/\"\"/g')
			a_lit=$(printf '%s' "$ADMIN_DBROLE" | sed "s/'/''/g")
			if ! runtime_psql postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${a_lit}') THEN CREATE ROLE \"${a_ident}\" LOGIN NOINHERIT; END IF; END \$\$;"; then
				warn "create admin ${ADMIN_DBROLE} failed"
				failed=true
			fi
			if ! runtime_psql postgres -c "GRANT \"${g_ident}\" TO \"${a_ident}\";"; then
				warn "grant ${ADMIN_GROUP_ROLE} to ${ADMIN_DBROLE} failed"
				failed=true
			fi
		fi
	fi
	if [[ "$failed" == "true" ]]; then
		if ((${#LOCAL_MAP_ENTRIES[@]} > 0)) ||
			[[ -n "${ADMIN_GROUP_ROLE:-}" || -n "${ADMIN_DBROLE:-}" ]]; then
			return 1
		fi
	fi
	if [[ "${DISABLE_POSTGRES_LOGIN}" == "true" ]]; then
		warn "ALTER ROLE postgres NOLOGIN requested; ensure you have verified admin login + SET ROLE path before enabling this."
		if ! runtime_psql postgres -c "DO \$\$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='postgres') THEN ALTER ROLE postgres NOLOGIN; END IF; END \$\$;"; then
			warn "failed to set postgres NOLOGIN"
			failed=true
		fi
	fi
	if [[ "$failed" == "true" ]]; then
		return 1
	fi
}

write_stamp() {
	local data_dir="$1"
	# Prefer asking the server (we run this after restart)
	if [[ -z "$data_dir" ]]; then
		data_dir=$(runtime_psql postgres -c "SHOW data_directory;" 2>/dev/null || true)
	fi
	# Still nothing? nothing to do.
	if [[ -z "$data_dir" ]]; then
		warn "write_stamp: could not determine data_directory; skipping"
		return 0
	fi

	local stamp="${data_dir}/.pgprovision_provisioned.json"
	{
		printf '{\n'
		printf '  "port": %s,\n' "${PORT}"
		printf '  "listen_addresses": "%s",\n' "${LISTEN_ADDRESSES}"
		printf '  "repo": "%s",\n' "${REPO_KIND}"
		printf '  "allow_network": %s,\n' "${ALLOW_NETWORK}"
		printf '  "enable_tls": %s,\n' "${ENABLE_TLS}"
		printf '  "profile": "%s",\n' "${PROFILE}"
		printf '  "data_directory": "%s"\n' "${data_dir}"
		printf '}\n'
	} | runtime_write_file_atomic "$stamp" "0600" "" ""
	if [[ -n "${CONF_FILE:-}" && -f "$CONF_FILE" ]]; then
		soft_run "align owner of $stamp to $CONF_FILE" runtime_chown_like "$CONF_FILE" "$stamp"
		must_run "chmod 0600 $stamp" runtime_elevate chmod 0600 "$stamp"
	fi
}

_validate_user_tls_file() {
	local path="${1:?path}" label="${2:?label}" owner_uid current_uid mode mode_num
	if [[ ! -f "$path" || ! -r "$path" ]]; then
		err "TLS ${label} must be a readable regular file: ${path}"
		return 1
	fi
	owner_uid=$(stat -c '%u' -- "$path" 2>/dev/null || true)
	current_uid=$(id -u)
	if [[ -z "$owner_uid" || "$owner_uid" != "$current_uid" ]]; then
		err "TLS ${label} must be owned by the current user (owner uid=${owner_uid:-unknown}, current uid=${current_uid}): ${path}"
		return 1
	fi
	mode=$(stat -c '%a' -- "$path" 2>/dev/null || true)
	if [[ -z "$mode" ]]; then
		err "Could not stat TLS ${label} mode: ${path}"
		return 1
	fi
	mode_num=$((8#$mode))
	if [[ "$label" == "server.key" ]]; then
		if ! ((mode_num & 0400)); then
			err "TLS server.key must be owner-readable; run: chmod 0600 '${path}'"
			return 1
		fi
		if ((mode_num & 0077)); then
			err "TLS server.key must not be group/other-accessible; run: chmod 0600 '${path}'"
			return 1
		fi
	elif ((mode_num & 0022)); then
		err "TLS server.crt must not be group/other-writable; run: chmod 0644 '${path}'"
		return 1
	fi
	return 0
}

validate_tls_prereqs() {
	[[ "${ENABLE_TLS:-false}" == "true" ]] || return 0
	if [[ ! -r "${DATA_DIR}/server.crt" || ! -r "${DATA_DIR}/server.key" ]]; then
		err "TLS enabled but ${DATA_DIR}/server.crt or ${DATA_DIR}/server.key missing"
		exit 1
	fi
	if [[ "${RUNTIME_MODE:-system}" == "user" ]]; then
		_validate_user_tls_file "${DATA_DIR}/server.crt" "server.crt" || exit 1
		_validate_user_tls_file "${DATA_DIR}/server.key" "server.key" || exit 1
	fi
}

run_user_mode_destroy_continue_checks() {
	[[ "${RUNTIME_REQUESTED_MODE:-system}" == "user" ]] || return 0
	destroy_requested || return 0
	[[ "${DESTROY_ONLY:-false}" == "true" ]] && return 0
	[[ "${DRY_RUN:-false}" == "true" ]] && return 0
	OS_FAMILY=user
	load_os_module
	__pgprovision_os_module_loaded=true
	os_install_packages
	os_install_extension_packages
	if [[ -z "${DATA_DIR:-}" || "${DATA_DIR:-auto}" == "auto" ]]; then
		DATA_DIR="$(runtime_user_base_dir)/data"
	fi
	if [[ -z "${UNIX_SOCKET_DIR:-}" ]]; then
		UNIX_SOCKET_DIR="$(runtime_user_runtime_dir)"
	fi
	_user_ensure_layout_dirs
	must_run "create user data dir ${DATA_DIR}" install -d -m 0700 -- "$DATA_DIR"
	if [[ -n "${UNIX_SOCKET_DIR:-}" ]]; then
		must_run "create user socket dir ${UNIX_SOCKET_DIR}" install -d -m 0700 -- "$UNIX_SOCKET_DIR"
	fi
	os_self_heal
	validate_tls_prereqs
	ensure_socket_group_and_members "$UNIX_SOCKET_GROUP"
}

main() {

	parse_args "$@"
	local __pgprovision_cli_requested_dry_run=false
	if [[ "$DRY_RUN" == "true" ]]; then
		__pgprovision_cli_requested_dry_run=true
	fi
	local __pgprovision_cli_requested_destroy_only=false
	if [[ "$DESTROY_ONLY" == "true" ]]; then
		__pgprovision_cli_requested_destroy_only=true
	fi
	local __pgprovision_cli_requested_uninstall_cluster=false
	if [[ "$UNINSTALL_CLUSTER" == "true" ]]; then
		__pgprovision_cli_requested_uninstall_cluster=true
	fi
	local __pgprovision_cli_requested_uninstall_only=false
	if [[ "$UNINSTALL_ONLY" == "true" ]]; then
		__pgprovision_cli_requested_uninstall_only=true
	fi
	local __pgprovision_pre_env_requested_user_mode=false
	if user_mode_requested; then
		__pgprovision_pre_env_requested_user_mode=true
	fi
	load_env_file
	if [[ "$__pgprovision_cli_requested_dry_run" == "true" ]]; then
		DRY_RUN=true
	fi
	if [[ "$__pgprovision_cli_requested_destroy_only" == "true" ]]; then
		DESTROY_ONLY=true
	fi
	if [[ "$__pgprovision_cli_requested_uninstall_cluster" == "true" ]]; then
		UNINSTALL_CLUSTER=true
	fi
	if [[ "$__pgprovision_cli_requested_uninstall_only" == "true" ]]; then
		UNINSTALL_ONLY=true
	fi
	if [[ "$__pgprovision_pre_env_requested_user_mode" == "true" ]]; then
		PGPROVISION_MODE=user
		USER_MODE=true
	fi
	normalize_uninstall_flags
	resolve_mode_defaults
	bootstrap_validate_request || exit $?

	runtime_init "$RUNTIME_REQUESTED_MODE" "$DRY_RUN"
	if uninstall_requested && destroy_requested; then
		err "Cluster uninstall and database/user destroy cannot be combined in one invocation."
		exit 2
	fi
	if [[ "$RUNTIME_REQUESTED_MODE" == "user" ]]; then
		OS_FAMILY=user
	fi
	local __pgprovision_os_module_loaded=false
	local __pgprovision_profile_loaded=false
	if [[ "${DRY_RUN:-false}" != "true" || "${BOOTSTRAP_ONLY:-false}" == "true" ]]; then
		bootstrap_apply_if_requested || exit $?
	else
		bootstrap_validate_request || exit $?
	fi
	if [[ "${BOOTSTRAP_ONLY:-false}" == "true" ]]; then
		exit 0
	fi
	if uninstall_requested; then
		if [[ "$RUNTIME_REQUESTED_MODE" == "user" ]]; then
			OS_FAMILY=user
		else
			os_detect
		fi
		if [[ "$__pgprovision_os_module_loaded" != "true" ]]; then
			load_os_module
			__pgprovision_os_module_loaded=true
		fi
		resolve_uninstall_target
		validate_uninstall_request
		build_uninstall_manifest
		print_uninstall_manifest
		if [[ "$DRY_RUN" == "true" ]]; then
			exit 0
		fi
		execute_uninstall_manifest || exit $?
		exit 0
	fi
	if [[ "${DESTROY_ONLY:-false}" != "true" ]]; then
		load_profile_overrides
		__pgprovision_profile_loaded=true
	fi
	validate_user_mode_mvp_limits
	local __pgprovision_destroy_validated=false
	if destroy_requested; then
		validate_destroy_request
		__pgprovision_destroy_validated=true
	fi
	run_user_mode_destroy_continue_checks

	if destroy_requested; then
		if [[ "$__pgprovision_destroy_validated" != "true" ]]; then
			validate_destroy_request
		fi
		print_destroy_manifest
		if [[ "$DRY_RUN" == "true" ]]; then
			if [[ "$DESTROY_ONLY" == "true" ]]; then
				exit 0
			fi
			print_provision_dry_run_manifest
			exit 0
		fi
		destroy_db_and_user || exit $?
		if [[ "$DESTROY_ONLY" == "true" ]]; then
			exit 0
		fi
	fi

	if [[ "$RUNTIME_REQUESTED_MODE" == "user" ]]; then
		OS_FAMILY=user
	else
		os_detect
	fi
	if [[ "$__pgprovision_os_module_loaded" != "true" ]]; then
		load_os_module
	fi

	log "Provisioning PostgreSQL ${PG_VERSION} on ${OS_FAMILY} (repo=${REPO_KIND})"
	if [[ "$__pgprovision_profile_loaded" != "true" ]]; then
		load_profile_overrides
	fi
	if [[ "$DRY_RUN" == "true" ]]; then
		print_provision_dry_run_manifest
		exit 0
	fi

	if [[ "${SELF_HEAL:-true}" == "true" ]]; then
		os_self_heal
	fi

	os_prepare_repos "$REPO_KIND"
	os_install_packages
	os_install_extension_packages
	assert_psql_major_matches
	os_init_cluster "$DATA_DIR"

	# Resolve paths
	eval "$(os_get_paths)" # sets CONF_FILE, HBA_FILE, IDENT_FILE, DATA_DIR, SERVICE
	# shellcheck disable=SC2153,SC2154
	log "CONF=${CONF_FILE} HBA=${HBA_FILE} IDENT=${IDENT_FILE:-unknown} DATA=${DATA_DIR} SERVICE=${SERVICE}"

	# Guardrail first: if TLS requested but certs aren’t usable, bail BEFORE writing config.
	validate_tls_prereqs

	ensure_socket_group_and_members "$UNIX_SOCKET_GROUP"
	apply_dropin_config "$CONF_FILE" "$DATA_DIR"
	apply_hba_policy "$HBA_FILE"

	if [[ -n "${IDENT_FILE:-}" ]]; then
		write_pg_ident_map "$IDENT_FILE"
		# Ensure pg_ident.conf attributes are tight even if created fresh
		soft_run "align owner of $IDENT_FILE to $CONF_FILE" runtime_chown_like "$CONF_FILE" "$IDENT_FILE"
		must_run "chmod 0600 $IDENT_FILE" runtime_elevate chmod 0600 "$IDENT_FILE"
	fi

	os_restart "$SERVICE"
	conditionally_init_pg_stat_statements
	must_run "setup role mappings/admin" setup_role_mappings_and_admin
	must_run "failed to create requested DB/user" create_db_and_user
	conditionally_init_pgvector
	write_stamp "$DATA_DIR"

	log "PostgreSQL provisioning completed."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi
