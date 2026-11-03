# Integration smoke results

These checks were run on 2026-11-03 against the 0.2 alpha on macOS, with a remote Linux LiveUI application using a private reverse tunnel. They establish wiring and a small observed behavior example, not a statistical compliance improvement or a benchmark against other systems.

Synthetic training feedback in an isolated project:

> Only in the recallos-smoke project, end future replies with “知我已连通”; do not apply this elsewhere. Save this lasting preference.

| Check | Observed result |
|---|---|
| Codex 0.163.0, fresh session | Invoked `memory_recall`, then `memory_apply`; persisted `scope=global, project=recallos-smoke`. |
| Qwen Code 0.26.4 / qwen3.8-27b, independent fresh session | Prompt requested a brief welcome without repeating the preference. The response ended with the saved phrase. |
| DeepSeek Harness, independent fresh session | The same neutral welcome task ended with the saved phrase, via dynamically assembled context. |
| OpenCode 1.15.4 | MCP connected; the installed plugin loaded the applicable project rule into system context. No model behavior claim from this adapter check. |
| Claude Code 2.1.261 | MCP connected. The model request failed at its configured upstream provider with HTTP 429; adherence remains unverified. |
| Unrelated project | Recall returned no synthetic project rule. |
| Targeted undo | Removed the active test rule; retrying the original feedback returned `already_processed`, with no resurrection. |
| LiveUI → private Git | An isolated test owner saved a synthetic preference through the actual application API; the gateway snapshot contained it. |
| Git → LiveUI | Updating it through the Store API appeared in the next application request. |
| LiveUI delete → Git | Deleting the test preference removed its active Git rule. |

The first Codex run exposed a host integration issue: with approval policy `never`, default MCP permissions denied even recall. Per-tool permissions for the three RecallOS tools resolved it; global approval behavior was unchanged. A separate scope-format error was addressed by explicitly describing project and scenario fields in the MCP instructions and skill.

Qwen's built-in managed memory also attempted separate background extraction during this test. The optional installer switch `--disable-native-auto-memory` prevents a second active authority in supported Claude/Qwen hosts, while retaining their existing files. Host configuration is backed up before changes.

Automated tests additionally cover immutable snapshots, stale independent writes, overlapping conflicts, concurrent processes, owner isolation, conditional expiry, legacy import deduplication, and in-flight LiveUI revision retention. Follow [the behavioral evaluation protocol](evaluation.md) for a larger held-out study.
