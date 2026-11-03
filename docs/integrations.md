# Harness integrations

The code is shared; configuration belongs to each host. These are explicit setup examples, not an automatic installer. Merge the indicated entries into existing configuration, preserving unrelated hooks and tools. Host hook trust/reload behavior still applies.

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

Alternatively, add `--scope research` and `--project alpha` to a project-specific hook command. The same project slug must be used by every harness. The system never guesses project identity from the basename of a working directory.

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

This release ships no HTTP listener, OAuth server, or hosted plugin. ChatGPT web cannot connect to a local stdio process directly. A future authenticated remote adapter can expose the same Store operations, with one authoritative writer. Follow the current [ChatGPT plugin setup](https://developers.openai.com/plugins/quickstart) for the supported publishing and invocation path.

Do not describe the local stdio example as a working hosted ChatGPT integration. Likewise, MCP tools do not receive all conversations automatically: a host must actually invoke them or a lifecycle integration must pass the relevant data.
