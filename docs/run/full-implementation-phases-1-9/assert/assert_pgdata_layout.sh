#!/usr/bin/env bash
set -euo pipefail

data_dir="${1:?usage: assert_pgdata_layout.sh DIR}"
test -f "${data_dir}/PG_VERSION"
test -f "${data_dir}/global/pg_control"
