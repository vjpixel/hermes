# Diagnosis: vjpixel/hermes#11 — ~26 GB OOM, 4 testes em 2 arquivos

Status: BLOCKED (cause not identified — measurement rejected MagicMock hypothesis).
Measured: 2026-09-08 by Pixel (CLI, repo hermes-agent, checkout shared — only this file added).

## Confirmed (from issue body + gh api)
- 4 expensive tests: `tests/hermes_cli/test_update_orphan_backend_reap.py` (2) and `test_web_ui_build.py` (2).
- Isolated runs cheap: reap 16 passed 1.10s; web_ui 24 passed 0.93s.
- Full-suite run kills process at ~26 GB anon-RSS (systemd OOM on tmux-spawn-*.scope).

## Measurement performed
- `systemd-run --user --pipe --wait -p MemoryMax=4G` (fail-soft, never kills the machine).
- Prefix of 60 files (hermes_cli + gateway, excluding the 2 expensive ones) via `pytest.main()` in-process.
- Memory peak 223.2 MB (inside 4G ceiling, 157 passed, 1 legitimate failure in `test_update_self_lock.py` — not a leak).
- `gc.get_objects()` count of `MagicMock`: BEFORE prefix = 0; AFTER prefix = 0; delta mock_calls = 0.

## Hypothesis tested and rejected
- "Patch vazando MagicMock global que acumula mock_calls" — NOT supported by data.
- No `MagicMock` instances survive after prefix; no growth in `mock_calls`.

## Blocker to fix
- Real mechanism requires either full-suite `tracemalloc` + `objgraph` snapshot over ~4-5k tests, or `gc.get_objects()` filtering of types that actually grow (sockets, threads, `_handlers`, import caches) after the full prefix.
- Running that under current ceilings risks repeating the OOM-kill reported in #11 (already killed 2 tmux sessions).
- Workaround (lotes de 40 arquivos via `systemd-run -p MemoryMax=4G`) remains valid.

## Verdict
- Not a MagicMock leak.
- Not safe to patch without identifying the growing object type.
- PR #? only registers this file; no code change to repo source.
