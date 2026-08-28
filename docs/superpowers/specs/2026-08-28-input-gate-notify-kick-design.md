# WAITING FOR INPUT: gate, notify, kick — design

**Date:** 2026-08-28  **Status:** accepted (brainstormed in-session)

## Problem

When an external loop parks on `status: WAITING FOR INPUT`, the scheduler keeps firing
`superagent-tick.sh` every interval (default 10m). The wrapper has no pre-screen for that state, so
**every fire launches a full `claude -p` / `agent` / `codex` session** that reads the skill, reads the
loop file, finds no `answer:`, and exits. That is a paid LLM no-op per interval for as long as the
human is away — the same pathology issue #18 fixed for `DONE` (0.4.6), left open for the parked state.

Two secondary gaps make the wait longer than it needs to be:

- **Nobody is told.** The only signal is a log line in a file unattended mode guarantees nobody is
  tailing; `console-watch.sh` only helps if a terminal is already watching.
- **Answering waits out the interval.** Writing `answer: <option>` into the loop file (monitor Path B)
  is only picked up on the next scheduled fire, up to one full interval later.

## Decision

Three small, independent changes to the shipped driver; no skill-logic change, no scheduler change.

1. **Bash gate before the session** (`superagent-tick.sh`). If the loop file says
   `WAITING FOR INPUT` and the `## Pending decision` section holds no `answer:` line, log one line and
   `exit 0` without launching the CLI. Polling continues (a `sed` on a file every interval — free);
   the durable-resume story is untouched: the moment an answer appears, the next fire runs the
   session as today. Knob: `SUPER_INPUT_GATE=true` (default).
   *Rejected:* self-disarm on `WAITING FOR INPUT` like `DONE` — a hand-written `answer:` would then
   silently never be consumed unless the operator remembered to re-arm.
2. **Notify once on the transition** (`superagent-tick.sh`). The wrapper snapshots `status` before the
   session and compares after. On a transition *into* `WAITING FOR INPUT` or `DONE` it fires
   `superagent_notify`: `SUPER_NOTIFY_CMD` (operator shell snippet — ntfy/Slack/Pushover curl, etc.,
   with `SUPERAGENT_EVENT`/`SUPERAGENT_SLUG`/`LOOP_FILE`/`SUPERAGENT_TITLE`/`SUPERAGENT_BODY` in its
   env) when set; otherwise a desktop notification via `osascript` (macOS) / `notify-send` (Linux)
   when available; otherwise log only. Transition detection means it fires exactly once — no
   "already notified" sidecar state. Never fails the tick.
3. **Answer + kick now** (`scripts/answer.sh <slug> <answer…>`). Writes `answer: <text>` directly under
   the `## Pending decision` heading **under the L3 lock** (refuses if a tick holds it, refuses if the
   loop is not `WAITING FOR INPUT`), then kicks one tick immediately via the registered scheduler
   entry (`launchctl kickstart` / `systemctl --user start --no-block`) so the loop resumes in seconds.
   `--no-kick` skips the kick. The kick logic is lifted into `_common.sh` (`superagent_kick_tick`) and
   reused by `launch.sh`. `superagent-monitor` recommends `answer.sh` as the primary answer path.

Net effect: a parked loop costs **zero LLM sessions** while it waits, the operator hears about it once
on the device/channel they choose, and one command both answers and resumes.

## Out of scope (follow-ups)

- A `WAITING FOR CI` bash gate (`gh run view --json status` before the session) — same shape, second
  step.
- Event-driven wake via launchd `WatchPaths` / a systemd `.path` unit on the loop file. The tick
  itself rewrites the loop file every run, so a path trigger would re-fire after every tick and needs
  its own status gate; the gate + kick above gets ~all the value without that subtlety.
- `scripts/README.md`'s stale "28 keys / 30m / inherit" facts (tracked separately).

## Compatibility

- Loop-file format unchanged. Existing armed loops pick up the gate/notify on their next fire after
  the plugin update (the wrapper is read from the plugin dir per fire — no re-arm needed).
- New `.superenv` keys, all with safe defaults: `SUPER_INPUT_GATE=true`, `SUPER_NOTIFY_CMD=` (empty).
- No new exit codes. The gate exits 0 (a legal clean no-op under superloop L2's teardown invariant).
