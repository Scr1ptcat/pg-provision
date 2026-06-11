# lib/bootstrap.sh
# shellcheck shell=bash
[[ ${__BOOTSTRAP_LIB_LOADED:-0} -eq 1 ]] && return 0
__BOOTSTRAP_LIB_LOADED=1

bootstrap_is_requested() {
	[[ -n "${PGPROVISION_BOOTSTRAP_TARBALL:-}" ]]
}

bootstrap_default_dir() {
	if [[ -n "${PGPROVISION_BOOTSTRAP_DIR:-}" ]]; then
		printf '%s\n' "$PGPROVISION_BOOTSTRAP_DIR"
	else
		printf '%s\n' "$(runtime_user_base_dir)/binaries"
	fi
}

bootstrap_normalize_sha256() {
	local hash="${1:-}"
	hash="${hash,,}"
	if [[ -z "$hash" ]]; then
		err "--bootstrap-sha256/PGPROVISION_BOOTSTRAP_SHA256 is required for every bootstrap tarball, including local files."
		return 2
	fi
	if [[ ! "$hash" =~ ^[0-9a-f]{64}$ ]]; then
		err "Bootstrap SHA256 must be a 64-character hex digest."
		return 2
	fi
	printf '%s\n' "$hash"
}

bootstrap_cache_dir() {
	local hash="${1:-${PGPROVISION_BOOTSTRAP_SHA256:-}}" base
	hash="$(bootstrap_normalize_sha256 "$hash")" || return $?
	base="$(bootstrap_default_dir)"
	printf '%s/%s/%s\n' "$base" "${PG_VERSION:-16}" "$hash"
}

bootstrap_source_is_url() {
	case "${1:-}" in
	http://* | https://*) return 0 ;;
	*) return 1 ;;
	esac
}

bootstrap_verify_sha256() {
	local tarball="${1:?tarball}" hash="${2:-${PGPROVISION_BOOTSTRAP_SHA256:-}}" actual
	hash="$(bootstrap_normalize_sha256 "$hash")" || return $?
	if ! command -v sha256sum >/dev/null 2>&1; then
		err "sha256sum is required to verify bootstrap tarballs."
		return 2
	fi
	if [[ ! -r "$tarball" || ! -f "$tarball" ]]; then
		err "Bootstrap tarball is not a readable regular file: $tarball"
		return 2
	fi
	actual="$(sha256sum -- "$tarball" | awk '{print $1}')"
	actual="${actual,,}"
	if [[ "$actual" != "$hash" ]]; then
		err "Bootstrap tarball checksum mismatch for ${tarball}"
		err "Expected SHA256: ${hash}"
		err "Actual SHA256:   ${actual:-unknown}"
		return 2
	fi
	return 0
}

bootstrap_resolve_source() {
	local source="${1:-${PGPROVISION_BOOTSTRAP_TARBALL:-}}" hash cache_dir dest partial
	if [[ -z "$source" ]]; then
		err "--bootstrap-tarball/PGPROVISION_BOOTSTRAP_TARBALL is required for bootstrap."
		return 2
	fi
	hash="$(bootstrap_normalize_sha256 "${PGPROVISION_BOOTSTRAP_SHA256:-}")" || return $?
	PGPROVISION_BOOTSTRAP_SHA256="$hash"
	if bootstrap_source_is_url "$source"; then
		if ! command -v curl >/dev/null 2>&1; then
			err "Remote bootstrap tarballs require curl, but curl is not available."
			return 2
		fi
		cache_dir="$(bootstrap_cache_dir "$hash")" || return $?
		install -d -m 0700 -- "$cache_dir" || return $?
		dest="${cache_dir}/source.tarball"
		partial="${dest}.$$"
		rm -f -- "$partial"
		if ! curl -fsSL --proto '=http,https' -- "$source" -o "$partial"; then
			rm -f -- "$partial"
			err "Failed to download bootstrap tarball: $source"
			return 2
		fi
		mv -f -- "$partial" "$dest" || return $?
		printf '%s\n' "$dest"
		return 0
	fi
	if [[ ! -r "$source" || ! -f "$source" ]]; then
		err "Bootstrap tarball is not a readable regular file: $source"
		return 2
	fi
	printf '%s\n' "$source"
}

bootstrap_python() {
	local python_bin
	python_bin="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
	if [[ -z "$python_bin" ]]; then
		err "python3 is required to safely extract bootstrap tarballs."
		return 2
	fi
	printf '%s\n' "$python_bin"
}

bootstrap_extract_to_cache() {
	local tarball="${1:?tarball}" hash="${2:-${PGPROVISION_BOOTSTRAP_SHA256:-}}" cache_dir extract_dir marker python_bin
	hash="$(bootstrap_normalize_sha256 "$hash")" || return $?
	cache_dir="$(bootstrap_cache_dir "$hash")" || return $?
	extract_dir="${cache_dir}/root"
	marker="${cache_dir}/.extracted-sha256"
	if [[ -f "$marker" && -d "$extract_dir" && "$(<"$marker")" == "$hash" ]]; then
		printf '%s\n' "$extract_dir"
		return 0
	fi
	python_bin="$(bootstrap_python)" || return $?
	rm -rf -- "$extract_dir"
	install -d -m 0700 -- "$extract_dir" || return $?
	if ! "$python_bin" - "$tarball" "$extract_dir" <<'PY'; then
import os
import pathlib
import stat
import sys
import tarfile

tarball = pathlib.Path(sys.argv[1])
dest = pathlib.Path(sys.argv[2]).resolve()


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def ensure_within(path: pathlib.Path) -> None:
    try:
        path.relative_to(dest)
    except ValueError:
        fail(f"unsafe tar member escapes extraction directory: {path}")


def safe_archive_path(name: str) -> pathlib.PurePosixPath:
    if not name:
        fail("unsafe empty tar member path")
    archive_path = pathlib.PurePosixPath(name)
    if archive_path.is_absolute() or any(part == ".." for part in archive_path.parts):
        fail(f"unsafe tar member path: {name}")
    return archive_path


try:
    with tarfile.open(tarball, "r:*") as archive:
        members = archive.getmembers()
        for member in members:
            archive_path = safe_archive_path(member.name)
            target = dest.joinpath(*archive_path.parts).resolve()
            ensure_within(target)
            if not (
                member.isfile()
                or member.isdir()
                or member.issym()
                or member.islnk()
            ):
                fail(f"unsupported tar member type: {member.name}")
            if member.issym() or member.islnk():
                link_path = safe_archive_path(member.linkname)
                if member.issym():
                    link_target = target.parent.joinpath(*link_path.parts).resolve()
                else:
                    link_target = dest.joinpath(*link_path.parts).resolve()
                ensure_within(link_target)
        for member in members:
            archive.extract(member, dest)
        for root, dirs, files in os.walk(dest):
            for name in [*dirs, *files]:
                path = pathlib.Path(root, name)
                mode = path.lstat().st_mode
                if not stat.S_ISLNK(mode):
                    os.chmod(path, stat.S_IMODE(mode) & ~0o6000)
except (tarfile.TarError, OSError) as exc:
    fail(f"failed to extract bootstrap tarball safely: {exc}")
PY
		rm -rf -- "$extract_dir"
		err "Bootstrap tarball extraction failed."
		return 2
	fi
	printf '%s\n' "$hash" >"$marker"
	printf '%s\n' "$extract_dir"
}

bootstrap_validate_required_binaries() {
	local bin_dir="${1:?bin_dir}" name
	local -a missing=()
	for name in postgres initdb pg_ctl psql; do
		if [[ ! -x "${bin_dir}/${name}" ]]; then
			missing+=("${bin_dir}/${name}")
		fi
	done
	if ((${#missing[@]} > 0)); then
		err "Bootstrap tarball required PostgreSQL binaries are missing or not executable: ${missing[*]}"
		return 2
	fi
}

bootstrap_find_pg_bin_dir() {
	local extract_dir="${1:?extract_dir}" postgres_bin bin_dir
	if [[ -x "${extract_dir}/bin/postgres" ]] && bootstrap_validate_required_binaries "${extract_dir}/bin"; then
		printf '%s\n' "${extract_dir}/bin"
		return 0
	fi
	while IFS= read -r postgres_bin; do
		bin_dir="$(dirname -- "$postgres_bin")"
		if bootstrap_validate_required_binaries "$bin_dir"; then
			printf '%s\n' "$bin_dir"
			return 0
		fi
	done < <(find "$extract_dir" -mindepth 2 -maxdepth 7 -path '*/bin/postgres' -print | sort)
	err "Bootstrap tarball must contain bin/postgres, bin/initdb, bin/pg_ctl, and bin/psql under one extracted root."
	return 2
}

bootstrap_binary_major() {
	local bin="${1:?binary}" output token
	output="$("$bin" --version 2>/dev/null || true)"
	for token in $output; do
		if [[ "$token" =~ ^[0-9]+([.][0-9]+)? ]]; then
			printf '%s\n' "${token%%.*}"
			return 0
		fi
	done
	return 1
}

bootstrap_validate_major() {
	local bin_dir="${1:?bin_dir}" expected="${2:-${PG_VERSION:-16}}" name major
	bootstrap_validate_required_binaries "$bin_dir" || return $?
	for name in postgres initdb pg_ctl psql; do
		major="$(bootstrap_binary_major "${bin_dir}/${name}")" || {
			err "Could not determine ${name} version from ${bin_dir}/${name} --version"
			return 2
		}
		if [[ "$major" != "$expected" ]]; then
			err "Expected bootstrapped ${name} PostgreSQL ${expected}.x, found major ${major} at ${bin_dir}/${name}"
			return 2
		fi
	done
}

bootstrap_validate_request() {
	if [[ "${BOOTSTRAP_ONLY:-false}" == "true" && -z "${PGPROVISION_BOOTSTRAP_TARBALL:-}" ]]; then
		err "--bootstrap-only requires --bootstrap-tarball."
		return 2
	fi
	bootstrap_is_requested || return 0
	if [[ "${RUNTIME_REQUESTED_MODE:-system}" != "user" ]]; then
		err "--bootstrap-tarball requires --user-mode or PGPROVISION_MODE=user; refusing to bootstrap in system mode."
		return 2
	fi
	PGPROVISION_BOOTSTRAP_SHA256="$(bootstrap_normalize_sha256 "${PGPROVISION_BOOTSTRAP_SHA256:-}")" || return $?
}

bootstrap_apply_if_requested() {
	local tarball extract_dir bin_dir
	bootstrap_validate_request || return $?
	bootstrap_is_requested || return 0
	tarball="$(bootstrap_resolve_source "${PGPROVISION_BOOTSTRAP_TARBALL:-}")" || return $?
	bootstrap_verify_sha256 "$tarball" "${PGPROVISION_BOOTSTRAP_SHA256:-}" || return $?
	extract_dir="$(bootstrap_extract_to_cache "$tarball" "${PGPROVISION_BOOTSTRAP_SHA256:-}")" || return $?
	bin_dir="$(bootstrap_find_pg_bin_dir "$extract_dir")" || return $?
	bootstrap_validate_major "$bin_dir" "${PG_VERSION:-16}" || return $?
	PG_BIN_DIR="$bin_dir"
	PGPROVISION_BOOTSTRAPPED_PG_BIN_DIR="$bin_dir"
	export PG_BIN_DIR PGPROVISION_BOOTSTRAPPED_PG_BIN_DIR
	log "Using bootstrapped PostgreSQL binaries: ${PG_BIN_DIR}"
}
