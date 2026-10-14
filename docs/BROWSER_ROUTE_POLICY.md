# Browser Route Policy

## Scope

This is the route-of-record for every browser-facing skill shipped with this
project: database search, authentication/session checks, pagination, result
parsing, record details, citation export, and full-text handoff. It applies to
new evidence syntheses and reproduction tasks whenever a browser is used.

## Route priority

1. **Codex built-in CDP browser first.** Start with the built-in browser and
   its supported browser actions in the active authenticated context. A helper
   skill's older Chrome DevTools MCP or API-first wording does not override
   this project-wide priority.
2. **Keep the session stable.** Use the same authenticated browser context for
   a database task. Record the browser route and session evidence with the
   task. Do not silently switch browser transports or sessions.
3. **Chrome DevTools is a documented fallback only.** Use it only when the
   built-in browser is unavailable or cannot perform a specific required
   operation. Record the attempted primary route and the concrete limitation
   before switching. Follow the loopback endpoint, dedicated non-default
   profile, and `/json/version` preflight in
   [`ENVIRONMENT_AND_APPLICATION_DEFAULTS.md`](ENVIRONMENT_AND_APPLICATION_DEFAULTS.md).
4. **Searches remain serial.** Protocol database searches go through
   `search/browser_search_queue.json`: one active task, no parallel browser
   calls. After reporting the current database's exact-as-run history and
   export evidence, wait for the user's confirmation before starting the next.
5. **Keep APIs in their declared role.** A database API may be used for
   protocol-recorded export or independent checking when that workflow allows
   it. It does not silently replace the required browser/session evidence.

When this policy conflicts with a database helper skill, this policy takes
precedence. Map that skill's operation onto the built-in CDP browser actions
available in the current Codex session. Use the documented Chrome DevTools
fallback only for the recorded capability gap.
