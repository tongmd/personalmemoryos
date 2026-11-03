import json
import tempfile
import threading
import tomllib
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from personalmemoryos.http_server import Gateway, make_server
from personalmemoryos.install import install
from personalmemoryos.store import Store


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.store = Store(self.home / "memory")
        self.base = self.store.init()["revision"]

    def test_attributes_preserve_conditions_and_expiration(self):
        self.store.apply(
            rule_id="reading",
            scope="liveui",
            text="Use large type",
            source_id="a",
            evidence="Large type at night",
            base_revision=self.base,
            attributes={
                "condition": "Night reading",
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(self.store.recall(["liveui"])["rules"], [])
        self.assertEqual(
            self.store.snapshot()["rules"][0]["attributes"]["condition"], "Night reading"
        )

    def test_gateway_owner_isolation(self):
        gateway = Gateway(self.store, "x" * 40, "primary")
        other = gateway.for_owner("other")
        other.apply(
            rule_id="language",
            scope="global",
            text="Use French",
            source_id="a",
            evidence="Use French",
            base_revision=other.head(),
        )
        self.assertEqual(
            gateway.dispatch({"owner": "primary", "operation": "snapshot"})["rules"], []
        )
        self.assertEqual(
            len(gateway.dispatch({"owner": "other", "operation": "snapshot"})["rules"]), 1
        )

    def test_http_requires_authentication_and_passes_rpc(self):
        gateway = Gateway(self.store, "x" * 40, "primary")
        server = make_server(gateway, 0)
        self.addCleanup(server.server_close)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/v1/memory"
        body = json.dumps({"owner": "primary", "operation": "snapshot"}).encode()
        request = urllib.request.Request(url, data=body)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 401)
        request.add_header("Authorization", "Bearer " + "x" * 40)
        with urllib.request.urlopen(request) as response:
            self.assertEqual(json.load(response)["revision"], self.base)

    def test_installer_preserves_existing_settings_and_is_idempotent(self):
        claude = self.home / ".claude/settings.json"
        claude.parent.mkdir()
        old = {
            "model": "existing-model",
            "env": {"EXAMPLE_KEY": "fixture"},
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command", "command": "existing-hook"}]}]
            },
        }
        claude.write_text(json.dumps(old))
        codex = self.home / ".codex/config.toml"
        codex.parent.mkdir()
        codex.write_text('model = "existing-model"\n')
        source = Path(__file__).resolve().parents[1]
        executable = source / ".venv/bin/recallos"
        first = install(self.home, source, executable)
        value = json.loads(claude.read_text())
        self.assertEqual(value["env"], old["env"])
        self.assertEqual(value["hooks"]["SessionStart"], old["hooks"]["SessionStart"])
        self.assertEqual(len(value["hooks"]["UserPromptSubmit"]), 1)
        self.assertTrue((Path(first["backup"]) / ".claude/settings.json").exists())
        second = install(self.home, source, executable)
        self.assertEqual(second["changed"], [])

    def test_automatic_permissions_are_limited_to_recallos_tools(self):
        settings = self.home / ".claude/settings.json"
        settings.parent.mkdir()
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Read"], "deny": ["Bash(rm *)"]}})
        )
        source = Path(__file__).resolve().parents[1]
        install(self.home, source, source / ".venv/bin/recallos", automatic_writes=True)
        config = tomllib.loads((self.home / ".codex/config.toml").read_text())
        tools = config["mcp_servers"]["recallos"]["tools"]
        self.assertEqual(set(tools), {"memory_recall", "memory_apply", "memory_revert"})
        self.assertTrue(all(t["approval_mode"] == "approve" for t in tools.values()))
        permissions = json.loads(settings.read_text())["permissions"]
        self.assertIn("Read", permissions["allow"])
        self.assertEqual(permissions["deny"], ["Bash(rm *)"])
        self.assertEqual(len(permissions["allow"]), 4)
