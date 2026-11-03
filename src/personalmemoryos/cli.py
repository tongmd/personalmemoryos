"""Small local CLI. JSON stdout is shared by people, hooks, and harnesses."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .hook import load_payload, project_from_cwd, run_hook
from .store import Conflict, MemoryError, Store, encode


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recallos", description="RecallOS · 知我 — scoped, Git-versioned personal memory"
    )
    p.add_argument("--store", default=os.environ.get("PMOS_STORE", "~/.personalmemoryos"))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize an empty private memory repository")
    sub.add_parser("revision", help="Get the current snapshot revision")
    recall = sub.add_parser("recall", help="Read a consistent scoped snapshot")
    recall.add_argument("--scope", action="append", default=[])
    recall.add_argument("--project")
    recall.add_argument("--revision")
    recall.add_argument("--query")
    sub.add_parser("snapshot", help="Read all records for a trusted application adapter")
    apply = sub.add_parser("apply", help="Apply one structured feedback update")
    apply.add_argument("--id", required=True, dest="rule_id")
    apply.add_argument("--scope", default="global")
    apply.add_argument("--project")
    value = apply.add_mutually_exclusive_group(required=True)
    value.add_argument("--text")
    value.add_argument("--delete", action="store_true")
    apply.add_argument("--source", required=True, dest="source_id")
    apply.add_argument("--evidence", required=True)
    apply.add_argument("--base", required=True, dest="base_revision")
    revert = sub.add_parser(
        "revert", help="Undo a feedback update without forgetting processed events"
    )
    revert.add_argument("source_id")
    revert.add_argument("--request-id", required=True)
    revert.add_argument("--base", required=True, dest="base_revision")
    history = sub.add_parser("history", help="List memory commits")
    history.add_argument("--limit", type=int, default=20)
    hook = sub.add_parser("hook", help="Read UserPromptSubmit JSON from stdin")
    hook.add_argument("--scope", action="append")
    hook.add_argument("--project")
    sub.add_parser("serve", help="Run the optional local MCP server over stdio")
    http = sub.add_parser("serve-http", help="Run an authenticated loopback RPC adapter")
    http.add_argument("--port", type=int, default=19504)
    http.add_argument("--token-file", required=True)
    http.add_argument("--shared-owner", required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    store = Store(args.store)
    try:
        if args.command == "init":
            result = store.init()
        elif args.command == "revision":
            result = {"revision": store.head()}
        elif args.command == "recall":
            result = store.recall(
                args.scope, args.project or project_from_cwd(), args.revision, args.query
            )
        elif args.command == "snapshot":
            result = store.snapshot()
        elif args.command == "apply":
            result = store.apply(
                rule_id=args.rule_id,
                text=None if args.delete else args.text,
                scope=args.scope,
                project=args.project,
                source_id=args.source_id,
                evidence=args.evidence,
                base_revision=args.base_revision,
            )
        elif args.command == "revert":
            result = store.revert(
                args.source_id, request_id=args.request_id, base_revision=args.base_revision
            )
        elif args.command == "history":
            result = store.history(args.limit)
        elif args.command == "hook":
            result = run_hook(store, load_payload(sys.stdin.read()), args.scope, args.project)
        elif args.command == "serve-http":
            from .http_server import serve_http

            serve_http(store, args.port, args.token_file, args.shared_owner)
            return 0
        else:
            from .mcp_server import serve

            serve(store)
            return 0
        sys.stdout.write(encode(result))
        return 0
    except (MemoryError, json.JSONDecodeError, OSError) as exc:
        # Hooks report failures visibly with exit 2; they never inject an empty
        # success snapshot when the configured store is unavailable.
        error = {"error": str(exc), "type": "conflict" if isinstance(exc, Conflict) else "error"}
        sys.stderr.write(encode(error))
        return 3 if isinstance(exc, Conflict) else 2


if __name__ == "__main__":
    raise SystemExit(main())
