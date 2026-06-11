#!/usr/bin/env bash
set -euo pipefail

sed -n 's/^confirm_token=//p' "${1:-/dev/stdin}" | tail -n1
