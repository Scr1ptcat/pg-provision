#!/usr/bin/env bash
set -euo pipefail

pattern="${1:?usage: assert_spl_excludes.sh PATTERN}"
spl="$(psql -XAt -c "SHOW shared_preload_libraries;")"
if grep -E -q -- "$pattern" <<<"$spl"; then
	echo "shared_preload_libraries unexpectedly matched ${pattern}: ${spl}" >&2
	exit 1
fi
