#!/usr/bin/env bash
set -euo pipefail

if rg 'pip install pg-provision' README.md docs/test-plan-rhel.md docs/pre-commit.md; then
	echo "unexpected pip user install path in operator docs" >&2
	exit 1
fi

bad_workflow_refs="$(
	awk '
		/^  [A-Za-z0-9_-]+:$/ {
			job = $1
			sub(/:$/, "", job)
		}
		/pip install/ {
			if (job != "integration-ubuntu-smoke" &&
			    job != "user-mode-smoke" &&
			    job != "integration-ubuntu-destructive") {
				printf "%d:%s\n", NR, $0
			}
		}
	' .github/workflows/ci.yml
)"

if [[ -n "$bad_workflow_refs" ]]; then
	echo "unexpected pip install outside frozen Ubuntu workflow jobs:" >&2
	echo "$bad_workflow_refs" >&2
	exit 1
fi

echo "ok: no pip user path in RHEL/Fedora operator surfaces"
