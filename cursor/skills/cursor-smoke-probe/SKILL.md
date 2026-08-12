---
name: cursor-smoke-probe
description: Use when asked to run the cursor smoke probe (or "superagent cursor probe") — verifies the Cursor build of the superagent plugin is loaded and reports environment facts for the port smoke test.
---

# Cursor smoke probe

Perform these checks with your file/shell tools, then output ONLY the report block below —
no extra prose before or after it.

1. Determine this skill file's own location and derive `plugin_root` = the directory two levels
   above it (the directory containing `skills/` and `templates/`). If you cannot determine the
   file's location, report `unknown`.
2. Check whether `<plugin_root>/templates/superenv.default` is readable; capture its first line.
3. Check whether `<plugin_root>/skills/superloop/SKILL.md` exists, and whether that file contains
   the string "CronCreate" (a correct Cursor build must NOT contain it; this probe file does not
   count).
4. Report the CLAUDE_PLUGIN_ROOT environment variable: `echo "${CLAUDE_PLUGIN_ROOT:-unset}"`.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_contains_croncreate: <yes|no>
    env_claude_plugin_root: <value, or unset>
    PROBE-END
