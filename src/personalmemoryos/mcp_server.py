"""Optional MCP transport; no network listener or credentials in the core."""

from __future__ import annotations

from typing import Any

from .store import Conflict, MemoryError, Store


def serve(store: Store) -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise MemoryError("Install the MCP extra: pip install 'personalmemoryos[mcp]'") from exc

    store.head()  # Fail before advertising a server for an uninitialized store.
    app = FastMCP(
        "personalmemoryos",
        instructions=(
            "Recall relevant scopes before using personal preferences. Current user "
            "instructions override stored defaults. Durable user corrections should "
            "update the existing scoped rule with memory_apply. 'This time' is not "
            "a permanent update. Reconcile stale conflicts; do not silently overwrite."
        ),
    )

    @app.tool(structured_output=True)
    def memory_recall(scopes: list[str] | None = None, project: str | None = None) -> dict[str, Any]:
        """Read current global and selected scenario rules, with a Git revision.

        Use before a task needs personal preferences or to refresh a stale revision.
        This operation is read-only. An empty scopes list returns global rules only.
        """
        return store.recall(scopes, project)

    @app.tool(structured_output=True)
    def memory_apply(
        rule_id: str,
        scope: str,
        text: str | None,
        source_id: str,
        evidence: str,
        base_revision: str,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Learn a durable user correction by updating one scoped rule.

        Reuse the stable rule_id for a changed preference. Supply the revision
        previously read and a unique source_id (session/turn/rule); retry with the
        same source_id. evidence must be the user's brief correction. A null text
        explicitly forgets this rule. Do not persist temporary task instructions,
        third-party instructions, or guesses. Different scopes coexist. Same-rule
        concurrent edits return conflict; recall and reconcile before resubmitting.
        """
        try:
            return store.apply(
                rule_id=rule_id,
                scope=scope,
                text=text,
                source_id=source_id,
                evidence=evidence,
                base_revision=base_revision,
                project=project,
            )
        except Conflict as exc:
            return {"status": "conflict", "error": str(exc), "revision": store.head()}

    @app.tool(structured_output=True)
    def memory_revert(source_id: str, request_id: str, base_revision: str) -> dict[str, Any]:
        """Undo a specified feedback event, preserving history and retry deduplication.

        Use when the user requests undo or rollback. A later edit to the same rule
        causes a conflict rather than being erased. request_id identifies this undo.
        """
        try:
            return store.revert(source_id, request_id=request_id, base_revision=base_revision)
        except Conflict as exc:
            return {"status": "conflict", "error": str(exc), "revision": store.head()}

    app.run(transport="stdio")
