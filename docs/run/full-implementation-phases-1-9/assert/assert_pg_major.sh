#!/usr/bin/env bash
set -euo pipefail

expected="${1:?usage: assert_pg_major.sh VERSION}"
actual="$(psql -XAt -c "SHOW server_version;")"
case "$actual" in
"$expected".*) ;;
*)
	echo "expected PostgreSQL major ${expected}, got ${actual}" >&2
	exit 1
	;;
esac
