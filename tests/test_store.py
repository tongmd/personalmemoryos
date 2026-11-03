import json
import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from personalmemoryos.hook import run_hook
from personalmemoryos.store import Conflict, MemoryError, Store


def write_in_process(path, base, number):
    return Store(path).apply(
        rule_id=f"rule-{number}",
        text=f"Value {number}",
        scope="global",
        source_id=f"process-{number}",
        evidence="Explicit user feedback",
        base_revision=base,
    )


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private-memory")
        self.initial = self.store.init()["revision"]

    def apply(
        self,
        rule_id="answer.language",
        text="Use Chinese",
        scope="global",
        source="session/1",
        base=None,
        project=None,
    ):
        return self.store.apply(
            rule_id=rule_id,
            text=text,
            scope=scope,
            source_id=source,
            evidence="以后这样做",
            base_revision=base or self.store.head(),
            project=project,
        )

    def test_persists_to_new_store_instance(self):
        result = self.apply()
        reopened = Store(self.store.path).recall()
        self.assertEqual(reopened["revision"], result["revision"])
        self.assertEqual(reopened["rules"][0]["text"], "Use Chinese")

    def test_scopes_and_projects_do_not_leak(self):
        self.apply()
        self.apply("answer.detail", "Cite primary research", "research", "session/2")
        self.apply("tests.runner", "Use pytest", "coding", "session/3", project="alpha")
        self.assertEqual(len(self.store.recall()["rules"]), 1)
        self.assertEqual(len(self.store.recall(["research"])["rules"]), 2)
        self.assertEqual(len(self.store.recall(["coding"], "beta")["rules"]), 1)
        self.assertEqual(len(self.store.recall(["coding"], "alpha")["rules"]), 2)

    def test_stale_independent_updates_merge(self):
        self.apply(base=self.initial)
        self.apply("answer.length", "Be concise", source="session/2", base=self.initial)
        self.assertEqual(len(self.store.recall()["rules"]), 2)

    def test_stale_same_rule_rejected_without_writes(self):
        self.apply(base=self.initial)
        revision = self.store.head()
        with self.assertRaises(Conflict):
            self.apply(text="Use English", source="session/2", base=self.initial)
        self.assertEqual(self.store.head(), revision)
        self.assertEqual(self.store.git("status", "--porcelain"), "")

    def test_same_value_concurrent_feedback_is_recorded(self):
        self.apply(base=self.initial)
        result = self.apply(source="session/2", base=self.initial)
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(len(self.store.recall()["rules"]), 1)

    def test_retry_is_idempotent(self):
        first = self.apply()
        second = self.apply(base=self.initial)
        self.assertEqual(second["status"], "already_processed")
        self.assertEqual(first["revision"], second["revision"])

    def test_source_id_cannot_be_reused_for_another_patch(self):
        self.apply()
        with self.assertRaises(Conflict):
            self.apply(text="Use English")

    def test_rollback_and_retry_cannot_resurrect_rule(self):
        self.apply()
        self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual(self.store.recall()["rules"], [])
        result = self.apply(base=self.initial)
        self.assertEqual(result["status"], "already_processed")
        self.assertEqual(self.store.recall()["rules"], [])

    def test_rollback_preserves_other_rules(self):
        self.apply()
        self.apply("answer.length", "Be concise", source="session/2")
        self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual([r["id"] for r in self.store.recall()["rules"]], ["answer.length"])

    def test_rollback_does_not_destroy_newer_edit(self):
        self.apply()
        self.apply(text="Use English", source="session/2")
        with self.assertRaises(Conflict):
            self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual(self.store.recall()["rules"][0]["text"], "Use English")

    def test_rollback_restores_previous_value(self):
        self.apply()
        self.apply(text="Use English", source="session/2")
        self.store.revert("session/2", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual(self.store.recall()["rules"][0]["text"], "Use Chinese")

    def test_rollback_retry_is_idempotent(self):
        self.apply()
        first = self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        second = self.store.revert("session/1", request_id="undo/1", base_revision=self.initial)
        self.assertEqual(first["revision"], second["revision"])

    def test_explicit_delete_and_undo(self):
        self.apply()
        self.apply(text=None, source="session/2")
        self.assertEqual(self.store.recall()["rules"], [])
        self.store.revert("session/2", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual(self.store.recall()["rules"][0]["text"], "Use Chinese")

    def test_noop_forget_can_be_undone(self):
        self.apply(text=None)
        self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        self.assertEqual(self.store.recall()["rules"], [])

    def test_failed_commit_restores_files(self):
        original = self.store.git

        def fail_commit(*args, **kwargs):
            if args[0] == "commit":
                raise MemoryError("Simulated commit failure")
            return original(*args, **kwargs)

        with (
            patch.object(self.store, "git", side_effect=fail_commit),
            self.assertRaises(MemoryError),
        ):
            self.apply()
        self.assertEqual(self.store.head(), self.initial)
        self.assertEqual(self.store.git("status", "--porcelain", "--untracked-files=all"), "")

    def test_old_snapshot_remains_consistent(self):
        first = self.apply()["revision"]
        self.apply(text="Use English", source="session/2")
        self.assertEqual(self.store.recall(revision=first)["rules"][0]["text"], "Use Chinese")

    def test_cross_process_writers_do_not_lose_updates(self):
        with ProcessPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(write_in_process, str(self.store.path), self.initial, i)
                for i in range(8)
            ]
            for future in futures:
                future.result(timeout=30)
        self.assertEqual(len(self.store.recall()["rules"]), 8)

    def test_reader_during_writes_gets_committed_snapshots(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(write_in_process, str(self.store.path), self.initial, 1)
            snapshot = self.store.recall()
            writer.result(timeout=10)
        self.assertIn(len(snapshot["rules"]), (0, 1))
        self.assertEqual(self.store.recall(revision=snapshot["revision"]), snapshot)

    def test_manual_uncommitted_changes_are_preserved(self):
        path = self.store.path / "MEMORY.md"
        path.write_text("My manual notes\n")
        with self.assertRaises(MemoryError):
            self.apply()
        self.assertEqual(path.read_text(), "My manual notes\n")

    def test_path_traversal_rejected(self):
        for value in ("../../other", "--help", "a/b", "", "."):
            with self.subTest(value=value), self.assertRaises(MemoryError):
                self.apply(rule_id=value)

    def test_hook_hot_reload(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Help with research"}
        first = run_hook(self.store, payload)
        self.apply("evidence", "Cite data", "research")
        second = run_hook(self.store, payload)
        self.assertNotEqual(first, second)
        self.assertIn("Cite data", second["hookSpecificOutput"]["additionalContext"])
        self.store.revert("session/1", request_id="undo/1", base_revision=self.store.head())
        third = run_hook(self.store, payload)
        self.assertNotIn("Cite data", third["hookSpecificOutput"]["additionalContext"])

    def test_same_id_can_have_scoped_exception(self):
        self.apply("answer.length", "Be concise")
        self.apply("answer.length", "Explain evidence in detail", "research", "session/2")
        self.assertEqual(len(self.store.recall(["research"])["rules"]), 2)
        self.assertEqual(len(self.store.recall(["coding"])["rules"]), 1)

    def test_git_environment_does_not_redirect_store(self):
        previous = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = "/does/not/exist"
        try:
            self.apply()
            self.assertEqual(len(self.store.recall()["rules"]), 1)
        finally:
            if previous is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = previous

    def test_cli_hook_protocol(self):
        result = subprocess.run(
            [
                os.sys.executable,
                "-m",
                "personalmemoryos.cli",
                "--store",
                str(self.store.path),
                "hook",
            ],
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "Hello"}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit"
        )


if __name__ == "__main__":
    unittest.main()
