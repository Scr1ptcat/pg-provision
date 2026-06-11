# lib/common.sh
# shellcheck shell=bash
[[ ${__COMMON_LIB_LOADED:-0} -eq 1 ]] && return 0
__COMMON_LIB_LOADED=1

_c_green=$'\033[0;32m'
_c_yellow=$'\033[0;33m'
_c_red=$'\033[0;31m'
_c_reset=$'\033[0m'

log() { echo -e "${_c_green}[pgprovision]${_c_reset} $*"; }
warn() { echo -e "${_c_yellow}[pgprovision][warn]${_c_reset} $*" 1>&2; }
err() { echo -e "${_c_red}[pgprovision][error]${_c_reset} $*" 1>&2; }
run() {
	echo "+ $*"
	"$@"
}

run_quiet() {
	"$@"
}

must_run() {
	local msg="$1"
	shift
	local rc=0
	run "$@" || {
		rc=$?
		err "$msg (rc=$rc)"
		exit "$rc"
	}
}

soft_run() {
	local msg="$1"
	shift
	local rc=0
	run "$@" || {
		rc=$?
		warn "$msg (rc=$rc)"
		return 0
	}
}

_as_root() {
	runtime_elevate "$@"
}

write_key_value_dropin() {
	local f="$1" key="$2" val="$3"
	runtime_elevate touch "$f"
	if runtime_elevate grep -E -q "^[[:space:]]*${key}[[:space:]]*=" "$f"; then
		runtime_elevate sed -i -E "s|^[[:space:]]*(${key})[[:space:]]*=.*$|\1 = ${val}|" "$f"
	else
		printf '%s\n' "${key} = ${val}" | runtime_elevate tee -a "$f" >/dev/null
	fi
}

ensure_line() {
	local f="$1"
	shift
	local line="$*"
	runtime_elevate touch "$f"
	if ! runtime_elevate grep -Fqx -- "$line" "$f" 2>/dev/null; then
		printf '%s\n' "$line" | runtime_elevate tee -a "$f" >/dev/null
	fi
}

ensure_dir() {
	local d="$1"
	if [[ -d "$d" ]]; then
		echo "+ dir exists: $d"
		return 0
	fi
	if install -d -m 0755 "$d" 2>/dev/null; then
		echo "+ install -d -m 0755 $d"
		return 0
	fi
	if runtime_elevate install -d -m 0755 "$d"; then
		return 0
	else
		err "Cannot create directory $d (no permission or sudo)"
		exit 1
	fi
}
