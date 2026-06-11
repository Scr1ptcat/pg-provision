# uv user install (RHEL/Fedora) — orchestrator STATE (overwrite each phase boundary)

phase: 4 status: blocked
items: closed:[0-start-state,1-docs,2-ci-pip-elimination-code,3-fedora-user-mode-code,3-local-fedora-user-mode-smoke,4-reference-sweep,4-full-local-gate] open:[2-ci-pip-elimination-pr-ci,3-fedora-user-mode-main-green,3-publish-gate-after-main-green] deferred:[5-post-publish-pypi]
code: HEAD dde6ef9 env_built: y pytest: green pre-commit: green
ci: pr_url: n/a fedora-smoke: local-code-green/pr-pending build: local-code-green/pr-pending
fedora-user-mode-smoke: local-container-green/not-yet-on-main publish_needs_updated: n
decisions_open: [resolved: pg-major=drift, tarball-ci=defer, phase5=defer]
in_flight: []
next_action: Commit/push these changes, open PR, watch `fedora-smoke`, `build`, and `fedora-user-mode-smoke`; after the job is green on `main`, make a follow-up change adding `fedora-user-mode-smoke` to `publish.needs`.
