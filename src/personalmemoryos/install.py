"""Idempotent host setup with private backups and additive config edits."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from .store import MemoryError, Store, encode


def install(
    home: Path,
    source: Path,
    executable: Path,
    qwen_home: Path | None = None,
    automatic_writes: bool = False,
    disable_native_auto_memory: bool = False,
) -> dict:
    backup = home / ".personalmemoryos-backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    backup.mkdir(parents=True, mode=0o700)
    changed = []

    def write(path: Path, content: str):
        if path.exists() and path.read_text() == content:
            return
        if path.exists():
            saved = backup / path.relative_to(home)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".recallos-tmp")
        temporary.write_text(content)
        temporary.chmod(0o600)
        temporary.replace(path)
        changed.append(str(path))

    def merge_json(path: Path, mutate):
        value = json.loads(path.read_text()) if path.exists() else {}
        mutate(value)
        write(path, encode(value))

    command = str(executable)
    hook = {"type": "command", "command": shlex.quote(command) + " hook", "timeout": 10}

    def add_hook(value):
        groups = value.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
        if not any(
            h.get("command") == hook["command"] for group in groups for h in group.get("hooks", [])
        ):
            groups.append({"hooks": [hook]})

    codex = home / ".codex/config.toml"
    text = codex.read_text() if codex.exists() else ""
    config = tomllib.loads(text)
    if "recallos" not in config.get("mcp_servers", {}):
        text += (
            "\n[mcp_servers.recallos]\ncommand = " + json.dumps(command) + '\nargs = ["serve"]\n'
        )
        tomllib.loads(text)
    if automatic_writes:
        for tool in ("memory_recall", "memory_apply", "memory_revert"):
            current = tomllib.loads(text).get("mcp_servers", {}).get("recallos", {})
            if tool not in current.get("tools", {}):
                text += f'\n[mcp_servers.recallos.tools.{tool}]\napproval_mode = "approve"\n'
    tomllib.loads(text)
    write(codex, text)
    merge_json(home / ".codex/hooks.json", add_hook)

    def claude_settings(value):
        add_hook(value)
        if disable_native_auto_memory:
            value["autoMemoryEnabled"] = False
        if automatic_writes:
            allowed = value.setdefault("permissions", {}).setdefault("allow", [])
            for tool in ("memory_recall", "memory_apply", "memory_revert"):
                name = "mcp__recallos__" + tool
                if name not in allowed:
                    allowed.append(name)

    merge_json(home / ".claude/settings.json", claude_settings)

    def add_mcp(value):
        value.setdefault("mcpServers", {})["recallos"] = {"command": command, "args": ["serve"]}

    merge_json(home / ".claude.json", add_mcp)
    if qwen_home is not None and (qwen_home / "settings.json").exists():

        def qwen(value):
            add_hook(value)
            add_mcp(value)
            if disable_native_auto_memory:
                memory = value.setdefault("memory", {})
                memory["enableManagedAutoMemory"] = False
                memory["enableManagedAutoDream"] = False
            if automatic_writes:
                value["mcpServers"]["recallos"]["trust"] = True

        merge_json(qwen_home / "settings.json", qwen)

    opencode = home / ".config/opencode"
    if (opencode / "opencode.json").exists():

        def opencode_config(value):
            value.setdefault("mcp", {})["recallos"] = {
                "type": "local",
                "command": [command, "serve"],
                "enabled": True,
            }
            if automatic_writes:
                permissions = value.setdefault("permission", {})
                if not isinstance(permissions, dict):
                    raise MemoryError(
                        "OpenCode permission config must be an object for tool permissions"
                    )
                for tool in ("memory_recall", "memory_apply", "memory_revert"):
                    permissions.setdefault("recallos_" + tool, "allow")

        merge_json(opencode / "opencode.json", opencode_config)
        write(
            opencode / "plugins/recallos.mjs",
            (source / "integrations/opencode/recallos.mjs").read_text(),
        )

    for root in (
        home / ".codex/skills",
        home / ".claude/skills",
        *((qwen_home / "skills",) if qwen_home else ()),
    ):
        destination = root / "personal-memory"
        target = source / "skills/personal-memory"
        root.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() and destination.resolve() == target.resolve():
            continue
        if destination.exists() or destination.is_symlink():
            raise MemoryError(f"Existing skill would be replaced: {destination}")
        destination.symlink_to(target, target_is_directory=True)
        changed.append(str(destination))

    # Static startup fallback is useful before a host reloads newly added hooks.
    block = (
        "\n<!-- recallos:start -->\n"
        f"Use RecallOS · 知我 for persistent preferences. Before starting a task, use its memory_recall tool "
        f"or run `{command} recall` to obtain current rules; select matching scopes for the task. "
        "The per-turn RecallOS snapshot, when present, already supplies this context. "
        "Learn clear durable user corrections through memory_apply; this-time requests are temporary. "
        "Do not duplicate authoritative preferences in this file.\n<!-- recallos:end -->\n"
    )
    for path in (home / ".codex/AGENTS.md", home / ".claude/CLAUDE.md"):
        text = path.read_text() if path.exists() else ""
        if "<!-- recallos:start -->" not in text:
            write(path, text.rstrip() + "\n" + block)

    Store(home / ".personalmemoryos").init()
    return {"changed": changed, "backup": str(backup), "store": str(home / ".personalmemoryos")}


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--qwen-home", type=Path)
    parser.add_argument("--automatic-writes", action="store_true")
    parser.add_argument("--disable-native-auto-memory", action="store_true")
    args = parser.parse_args()
    try:
        print(
            encode(
                install(
                    args.home,
                    args.source,
                    args.executable,
                    args.qwen_home,
                    args.automatic_writes,
                    args.disable_native_auto_memory,
                )
            )
        )
    except (MemoryError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
