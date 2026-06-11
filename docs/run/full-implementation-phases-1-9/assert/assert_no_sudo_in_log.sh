#!/usr/bin/env bash
set -euo pipefail

log="${1:?usage: assert_no_sudo_in_log.sh LOG}"
if grep -E -q '(^|[[:space:]])sudo([[:space:]]|$)' "$log"; then
	echo "log contains sudo: ${log}" >&2
	exit 1
fi
