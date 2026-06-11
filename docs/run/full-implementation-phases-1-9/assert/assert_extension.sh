#!/usr/bin/env bash
set -euo pipefail

db="${1:?usage: assert_extension.sh DB EXT}"
ext="${2:?usage: assert_extension.sh DB EXT}"
found="$(psql -XAt -d "$db" -c "SELECT extname FROM pg_extension WHERE extname='${ext//\'/\'\'}';")"
if [[ "$found" != "$ext" ]]; then
	echo "expected extension ${ext} in database ${db}" >&2
	exit 1
fi
