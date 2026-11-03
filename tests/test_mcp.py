"""Real stdio client/server smoke test, optional when only core is installed."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from personalmemoryos.store import Store


@unittest.skipUnless(importlib.util.find_spec("mcp"), "MCP extra is not installed")
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_feedback_recall_and_rollback(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        with tempfile.TemporaryDirectory() as temporary:
            store = Store(Path(temporary) / "memory")
            revision = store.init()["revision"]
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "personalmemoryos.cli", "--store", str(store.path), "serve"],
            )
            async with (
                stdio_client(params) as (reader, writer),
                ClientSession(reader, writer) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual(
                    {t.name for t in tools.tools},
                    {"memory_recall", "memory_apply", "memory_revert"},
                )
                result = await session.call_tool(
                    "memory_apply",
                    {
                        "rule_id": "answer.evidence",
                        "scope": "research",
                        "text": "Show data",
                        "source_id": "mcp/turn-1",
                        "evidence": "For research, show data",
                        "base_revision": revision,
                    },
                )
                self.assertFalse(result.isError)
                updated = result.structuredContent
                self.assertEqual(updated["status"], "updated")
                recall = await session.call_tool("memory_recall", {"scopes": ["research"]})
                self.assertEqual(recall.structuredContent["rules"][0]["text"], "Show data")
                conflict = await session.call_tool(
                    "memory_apply",
                    {
                        "rule_id": "answer.evidence",
                        "scope": "research",
                        "text": "No data",
                        "source_id": "mcp/stale",
                        "evidence": "Different correction",
                        "base_revision": revision,
                    },
                )
                self.assertEqual(conflict.structuredContent["status"], "conflict")
                undo = await session.call_tool(
                    "memory_revert",
                    {
                        "source_id": "mcp/turn-1",
                        "request_id": "mcp/undo",
                        "base_revision": updated["revision"],
                    },
                )
                self.assertEqual(undo.structuredContent["status"], "reverted")
                self.assertEqual(Store(store.path).recall(["research"])["rules"], [])
