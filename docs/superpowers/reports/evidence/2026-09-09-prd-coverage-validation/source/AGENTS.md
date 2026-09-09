# Proposed disposable validation policy — revision v1

This directory contains draft source documents, not an initialized code project.
After user approval, copy these documents into the new disposable code repository
/private/tmp/prd-coverage-validation-20260909/repo and initialize a separate external
vault /private/tmp/prd-coverage-validation-20260909/vault using superagent:init.
Use only installed plugin /Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917.
Do not read the primary plugin repository .superenv or any private vault. Set all SUPER_ keys
explicitly for the disposable fixture; SUPER_GOAL_AUTOCONFIRM=false at PRD authoring.
All model roles: native Codex gpt-5.6-sol, high effort, isolated contexts.
Only local git repositories and local bare origins. Proposed scope exception to code A7:
local feature-branch review and merge replaces GitHub PR transport; external vault uses A7
local direct commits. No schedulers, remote services, package refresh, or production changes.
This exception becomes authorized only with author approval of this draft.
