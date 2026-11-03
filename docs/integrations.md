# Harness integrations

The code is shared; configuration belongs to each host. The additive installer below covers local hosts; manual examples explain the same wiring. Host hook trust/reload behavior still applies.

## Local Codex and Claude Code

Install the optional MCP extra and initialize the store first. Use an **absolute path** to the installed `pmos` executable; noninteractive hook environments may not inherit your shell PATH.

Both hosts can run this `UserPromptSubmit` hook:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/ABS/PATH/personalmemoryos/.venv/bin/pmos hook",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Claude Code: add the entry to your user `~/.claude/settings.json` or an appropriate project settings file. Codex: use a supported `hooks.json` location or translate to the inline config below. Check the current official [Codex hooks](https://learn.chatgpt.com/docs/hooks) and [Claude Code hooks](https://code.claude.com/docs/en/hooks) documentation for file locations, trust, and version requirements.

Codex inline example in `~/.codex/config.toml`:

```toml
[[hooks.UserPromptSubmit]]
[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "/ABS/PATH/personalmemoryos/.venv/bin/pmos hook"
timeout = 10

[mcp_servers.personalmemoryos]
command = "/ABS/PATH/personalmemoryos/.venv/bin/pmos"
args = ["serve"]
```

Claude Code MCP configuration shape:

```json
{
  "mcpServers": {
    "personalmemoryos": {
      "command": "/ABS/PATH/personalmemoryos/.venv/bin/pmos",
      "args": ["serve"]
    }
  }
}
```

Add this through your host's supported MCP settings/CLI. Load the supplied `skills/personal-memory/SKILL.md` as a local skill if the host supports it, or use its short workflow as persistent guidance. The hook also supplies the essential feedback-learning instructions. A configured tool is not a guarantee of invocation.

### Scenarios and projects

Without configuration, the hook recognizes starter research/coding/writing keywords in English and Chinese. This small router is intentionally transparent, not a semantic classifier. A follow-up like “continue” may not contain those keywords; configure scopes for an ongoing project or have the agent call `memory_recall` explicitly.

```bash
PMOS_SCOPES=research,writing /ABS/PATH/personalmemoryos/.venv/bin/pmos hook
PMOS_PROJECT=alpha /ABS/PATH/personalmemoryos/.venv/bin/pmos hook --scope coding
```

Alternatively, add `--scope research` and `--project alpha` to a project-specific hook command. A project root can contain `.recallos.json` with `{"project":"alpha"}`; hooks and CLI/MCP recall search ancestors for this explicit identity. Every harness should use the same project slug. A project-wide preference uses `scope="global", project="alpha"`; scenario-specific project rules use e.g. `scope="coding", project="alpha"`. Never encode the project in a scope such as `project:alpha`.

The hook returns a consistent snapshot and a revision. Its output cap is 24,000 characters; oversized snapshots fail visibly rather than silently dropping rules. On a backend failure the command exits 2. Hosts can handle failed hooks differently: confirm that your installed harness surfaces the error instead of assuming the task must be blocked.

### Hot changes

- Rule updates: next user turn reads a fresh snapshot.
- Existing turn: retains its initial snapshot; a user's direct correction takes precedence.
- Hook/MCP code or configuration changes: reload or restart according to the host.
- `AGENTS.md`, `CLAUDE.md`, and skills remain static entry points; do not keep independently editable copies of the same memory in them.

## MCP operations

`pmos serve` exposes three tools over **local stdio**:

```text
memory_recall(scopes?, project?)
memory_apply(rule_id, scope, text|null, source_id, evidence, base_revision, project?)
memory_revert(source_id, request_id, base_revision)
```

A null `text` explicitly forgets the active rule. A stale same-rule update returns `status: conflict` with the current revision. Read and reconcile the actual feedback before trying again; merely substituting the new hash would defeat conflict detection.

Use unique source IDs per feedback rule, for example `host/session/turn/answer.evidence`. Retries must reuse the same ID and payload. Reusing an ID for a different payload is rejected.

## Hosted ChatGPT and other remote clients

This release has a private application RPC gateway, but no HTTP MCP endpoint, OAuth server, or hosted plugin. ChatGPT web cannot connect to a local stdio process directly. The private RPC bridge described below is for trusted application servers, not a hosted ChatGPT connector.

Do not describe the local stdio example as a working hosted ChatGPT integration. Likewise, MCP tools do not receive all conversations automatically: a host must actually invoke them or a lifecycle integration must pass the relevant data.

## RecallOS installer and application gateway

`recallos` is the preferred command name; `pmos` remains an alias. To configure local Codex, Claude Code, and an existing OpenCode installation with additive changes and private backups:

```bash
python -m personalmemoryos.install --source /ABS/PATH/personalmemoryos --executable /ABS/PATH/personalmemoryos/.venv/bin/recallos
```

Pass `--qwen-home PATH` for a Qwen Code installation using a custom home. Add `--automatic-writes` to authorize the three local RecallOS tools without a per-call approval prompt. This adds per-tool Codex/Claude/OpenCode permissions and trusts this local Qwen MCP server, without changing global approval policies. Explicit existing Codex/OpenCode tool policies are preserved. Without this option, host approval can prevent automatic learning, especially in noninteractive sessions.

The installer preserves unrelated settings and hooks, adds MCP entries, installs the skill, and creates the private store. Codex requires trusting the exact new hook through its native review flow. Existing running harnesses may need a settings reload or a new session.

For one shared memory authority, `--disable-native-auto-memory` disables Claude's built-in auto memory and Qwen's managed auto-memory extraction/consolidation. Existing files are retained. This also stops automatic capture of other facts by those native systems; use RecallOS project-scoped rules for facts you intend to preserve. The option is explicit and independent of tool permissions. Claude's setting is documented in its [memory guide](https://code.claude.com/docs/en/memory); Qwen's installed settings schema defines `memory.enableManagedAutoMemory` and `memory.enableManagedAutoDream`.

OpenCode's plugin refreshes context before model requests. `integrations/dsh/recallos.mjs` provides a dynamic context plugin for DeepSeek Harness; mount it alongside a `@deepseek-ai/dsh-mcp-client` entry through the profile's `insert` overlay. Its context callback reads a fresh revision at assembly; it does not mutate prompts or provider credentials.

For a trusted LiveUI/application gateway, create a private random token file (mode 0600) and run:

```bash
recallos serve-http --token-file /PRIVATE/gateway-token --shared-owner YOUR_AUTHENTICATED_APP_USERNAME
```

The RPC listener binds **127.0.0.1:19504**. A trusted server calls `POST /v1/memory` with a bearer token and `{owner, operation, arguments}`. Supported operations are snapshot, recall, apply, revert, and history. Exactly the configured shared owner maps to the desktop store; other authenticated owners map to isolated private repositories. The upstream application must authenticate users. This token grants gateway authority and must never be shipped to a browser. A remote application should connect over a private tunnel; it may use a different forwarded port.

The LiveUI adapter performs idempotent one-time imports of legacy SQLite preferences, then uses Git as authoritative state. Existing conditions, app scopes, expiration dates, and evidence are retained. Original SQLite rows remain a migration backup; they are not a second active write destination. Import receipts prevent forgotten preferences from being reintroduced on restart.
