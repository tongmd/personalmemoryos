"""One local writer, immutable Git snapshots, and conflict-aware rule patches.

The agent interprets natural-language feedback. This module deliberately handles
structured state transitions, not guesses about what a person intended.
"""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class MemoryError(ValueError):
    """An actionable validation or storage error."""


class Conflict(MemoryError):
    """A stale patch overlaps a newer change; no change has been written."""


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def slug(value: str, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", value):
        raise MemoryError(f"{name} must be 1-80 lowercase letters, digits, dots, _ or -")
    return value


def required_text(value: str, name: str, limit: int = 8000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise MemoryError(f"{name} must be nonempty text of at most {limit} characters")
    if "\x00" in value:
        raise MemoryError(f"{name} contains a NUL byte")
    return value.strip()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()

    def git(self, *args: str, check: bool = True) -> str:
        # Do not inherit a host project's index, worktree, or repository override.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
        result = subprocess.run(
            ["git", "-C", str(self.path), "-c", "core.hooksPath=/dev/null", *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if check and result.returncode:
            raise MemoryError(result.stderr.strip() or "Git command failed")
        return result.stdout

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Sibling lock exists before git init and survives all history operations.
        lock_path = self.path.parent / (self.path.name + ".pmos.lock")
        with lock_path.open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def init(self) -> dict:
        with self.lock():
            if (self.path / ".git").exists():
                self._check_store()
                return {"revision": self.head(), "created": False}
            if self.path.exists() and any(self.path.iterdir()):
                raise MemoryError(
                    "Initialize an empty dedicated directory, not an existing project"
                )
            self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.git("init", "-b", "main")
            self.git("config", "user.name", "RecallOS")
            self.git("config", "user.email", "memory@localhost")
            self.git("config", "commit.gpgsign", "false")
            self.git("config", "core.autocrlf", "false")
            # Never configure a remote automatically: memory is private by default.
            (self.path / "store.json").write_text(encode({"format": 1}), encoding="utf-8")
            (self.path / "MEMORY.md").write_text(
                "# Personal memory\n\nNo rules yet.\n", encoding="utf-8"
            )
            self.git("add", "--", "store.json", "MEMORY.md")
            self.git("commit", "-m", "Initialize private memory store")
            return {"revision": self.head(), "created": True}

    def _check_store(self) -> None:
        if not (self.path / ".git").is_dir() or not (self.path / "store.json").is_file():
            raise MemoryError("Memory store is not initialized; run pmos init")
        if json.loads((self.path / "store.json").read_text()) != {"format": 1}:
            raise MemoryError("Unsupported memory store format")

    def head(self) -> str:
        self._check_store()
        return self.git("rev-parse", "--verify", "HEAD").strip()

    def revision(self, value: str) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{7,40}", value):
            raise MemoryError("revision must be a Git commit hash")
        resolved = self.git("rev-parse", "--verify", value + "^{commit}").strip()
        # Reject commits from unrelated branches, including orphaned histories.
        result = self.git("merge-base", resolved, "HEAD").strip()
        if result != resolved:
            raise MemoryError("revision is not an ancestor of the current memory history")
        return resolved

    def _read(self, revision: str, path: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(self.path), "cat-file", "-e", f"{revision}:{path}"],
            capture_output=True,
            check=False,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        )
        if result.returncode:
            return None
        return self.git("show", f"{revision}:{path}")

    @staticmethod
    def rule_path(rule_id: str, scope: str, project: str | None) -> str:
        slug(rule_id, "rule_id")
        slug(scope, "scope")
        if project is not None:
            slug(project, "project")
        prefix = f"rules/projects/{project}/{scope}" if project else f"rules/{scope}"
        return f"{prefix}/{rule_id}.md"

    @staticmethod
    def parse_rule(text: str) -> dict:
        parts = text.split("\n---\n", 1)
        if not text.startswith("---\n") or len(parts) != 2:
            raise MemoryError("Invalid rule Markdown frontmatter")
        rule = json.loads(parts[0][4:])
        rule["text"] = parts[1].strip()
        return rule

    def all_rules(self, revision: str) -> list[dict]:
        paths = self.git("ls-tree", "-r", "--name-only", revision, "--", "rules/").splitlines()
        if not paths:
            return []
        result = subprocess.run(
            ["git", "-C", str(self.path), "archive", "--format=tar", revision, "--", "rules/"],
            capture_output=True,
            check=False,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        )
        if result.returncode:
            raise MemoryError("Cannot read the memory snapshot archive")
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
            return [
                self.parse_rule(archive.extractfile(member).read().decode("utf-8"))
                for member in archive.getmembers()
                if member.isfile() and member.name.endswith(".md")
            ]

    def snapshot(self) -> dict:
        """All records for trusted adapters; scope selection remains the caller's job."""
        revision = self.head()
        return {"revision": revision, "rules": self.all_rules(revision)}

    def recall(
        self,
        scopes: list[str] | None = None,
        project: str | None = None,
        revision: str | None = None,
        query: str | None = None,
    ) -> dict:
        current = self.head()  # Capture once, then read only immutable objects.
        snapshot = self.revision(revision) if revision else current
        selected = set(scopes or []) | {"global"}
        for scope in selected:
            slug(scope, "scope")
        if project is not None:
            slug(project, "project")
        available = self.all_rules(snapshot)
        rules = [
            r
            for r in available
            if r["scope"] in selected and r.get("project") in (None, project) and self.active(r)
        ]
        if query:
            tokens = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2}", query.lower()))
            pinned = [r for r in rules if r["scope"] == "global"]
            optional = [r for r in rules if r["scope"] != "global"]
            scored = [(sum(token in encode(r).lower() for token in tokens), r) for r in optional]
            rules = pinned + [
                r
                for score, r in sorted(scored, key=lambda item: -item[0])[:12]
                if score or not r.get("attributes", {}).get("condition")
            ]
        # General defaults first, project/scenario-specific rules afterwards.
        rules.sort(key=lambda r: (bool(r.get("project")), r["scope"] != "global", r["id"]))
        return {
            "revision": snapshot,
            "scopes": sorted(selected),
            "project": project,
            "rules": rules,
            "available_scopes": sorted(
                {r["scope"] for r in available if r.get("project") in (None, project)}
            ),
        }

    @staticmethod
    def active(rule: dict) -> bool:
        expiry = rule.get("attributes", {}).get("expires_at")
        return not expiry or datetime.fromisoformat(expiry) > datetime.now(UTC)

    @staticmethod
    def _event_path(source_id: str) -> str:
        required_text(source_id, "source_id", 500)
        return "events/" + hashlib.sha256(source_id.encode()).hexdigest() + ".json"

    def _clean(self) -> None:
        if self.git("status", "--porcelain", "--untracked-files=all").strip():
            raise MemoryError(
                "Store has uncommitted changes. Review and commit or restore them first"
            )

    def _index(self) -> str:
        lines = ["# Personal memory", "", "Generated navigation; rule files are authoritative.", ""]
        for path in (
            sorted((self.path / "rules").rglob("*.md")) if (self.path / "rules").exists() else []
        ):
            rule = self.parse_rule(path.read_text(encoding="utf-8"))
            label = "/".join(filter(None, [rule.get("project"), rule["scope"], rule["id"]]))
            lines.append(f"- [{label}]({path.relative_to(self.path).as_posix()})")
        return "\n".join(lines) + "\n"

    def _commit(self, changes: dict[str, str | None], message: str) -> str:
        # Caller holds lock and has checked the worktree is clean. All reader
        # paths use Git objects, so working-file materialization is never read.
        previous = {}
        names = [*changes, "MEMORY.md"]
        try:
            for name, content in changes.items():
                path = self.path / name
                previous[name] = path.read_text(encoding="utf-8") if path.exists() else None
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
            index = self.path / "MEMORY.md"
            previous["MEMORY.md"] = index.read_text(encoding="utf-8")
            index.write_text(self._index(), encoding="utf-8")
            self.git("add", "-A", "--", *names)
            self.git("commit", "-m", message)
        except BaseException:
            self.git("reset", "HEAD", "--", *names, check=False)
            for name, old in previous.items():
                path = self.path / name
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(old, encoding="utf-8")
            raise
        return self.head()

    def apply(
        self,
        *,
        rule_id: str,
        text: str | None,
        scope: str,
        source_id: str,
        evidence: str,
        base_revision: str,
        project: str | None = None,
        attributes: dict | None = None,
    ) -> dict:
        path = self.rule_path(rule_id, scope, project)
        evidence = required_text(evidence, "evidence", 2000)
        if text is not None:
            text = required_text(text, "text")
        request = {
            "rule_id": rule_id,
            "text": text,
            "scope": scope,
            "project": project,
            "evidence": evidence,
        }
        if attributes is not None:
            if not isinstance(attributes, dict) or len(encode(attributes)) > 8000:
                raise MemoryError("attributes must be a JSON object of at most 8000 characters")
            expiry = attributes.get("expires_at")
            if expiry:
                try:
                    parsed = datetime.fromisoformat(expiry)
                    if parsed.tzinfo is None:
                        raise ValueError("timezone is required")
                except (ValueError, TypeError) as exc:
                    raise MemoryError("expires_at must be an ISO timestamp with timezone") from exc
            request["attributes"] = attributes
        digest = hashlib.sha256(encode(request).encode()).hexdigest()
        event_path = self._event_path(source_id)
        with self.lock():
            current = self.head()
            self._clean()
            existing = self._read(current, event_path)
            if existing:
                event = json.loads(existing)
                if event.get("request_hash") != digest:
                    raise Conflict("source_id already refers to a different request")
                return {"revision": current, "status": "already_processed", "source_id": source_id}
            base = self.revision(base_revision)
            before = self._read(current, path)
            original = self._read(base, path)
            old_attributes = self.parse_rule(before).get("attributes", {}) if before else {}
            desired_attributes = old_attributes if attributes is None else attributes
            same_value = (before is None and text is None) or (
                before is not None
                and self.parse_rule(before)["text"] == text
                and old_attributes == desired_attributes
            )
            if before != original and not same_value:
                raise Conflict(
                    f"Rule changed since {base[:12]}; recall latest and reconcile feedback"
                )
            metadata = {
                "id": rule_id,
                "scope": scope,
                "project": project,
                "source_id": source_id,
                "evidence": evidence,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            if desired_attributes:
                metadata["attributes"] = desired_attributes
            after = (
                before
                if same_value
                else (
                    "---\n" + encode(metadata) + "---\n" + text + "\n" if text is not None else None
                )
            )
            event = {
                "kind": "feedback",
                "source_id": source_id,
                "request_hash": digest,
                "base_revision": base,
                "path": path,
                "before": before,
                "after": after,
            }
            changes = {event_path: encode(event)}
            if before != after:
                changes[path] = after
            revision = self._commit(changes, f"Remember {scope}/{rule_id}")
            return {
                "revision": revision,
                "status": "recorded" if same_value else "updated",
                "source_id": source_id,
                "rule_id": rule_id,
            }

    def revert(self, source_id: str, *, request_id: str, base_revision: str) -> dict:
        target_path = self._event_path(source_id)
        request_path = self._event_path(request_id)
        if source_id == request_id:
            raise MemoryError("Use a new request_id for the rollback")
        with self.lock():
            current = self.head()
            self._clean()
            seen = self._read(current, request_path)
            if seen:
                if json.loads(seen).get("reverts") != source_id:
                    raise Conflict("request_id already refers to a different operation")
                return {"revision": current, "status": "already_processed"}
            target_text = self._read(current, target_path)
            if not target_text:
                raise MemoryError("Unknown feedback source_id")
            target = json.loads(target_text)
            if target["kind"] != "feedback":
                raise MemoryError("Only feedback events can be reverted")
            self.revision(base_revision)
            path = target["path"]
            before = self._read(current, path)
            if before != target["after"]:
                raise Conflict("Rule changed after this feedback; reconcile before reverting")
            event = {
                "kind": "revert",
                "source_id": request_id,
                "reverts": source_id,
                "path": path,
                "before": before,
                "after": target["before"],
            }
            changes = {request_path: encode(event)}
            if before != target["before"]:
                changes[path] = target["before"]
            revision = self._commit(
                changes, f"Revert feedback {hashlib.sha256(source_id.encode()).hexdigest()[:12]}"
            )
            return {"revision": revision, "status": "reverted", "reverts": source_id}

    def history(self, limit: int = 20) -> list[dict]:
        self._check_store()
        if not 1 <= limit <= 1000:
            raise MemoryError("limit must be between 1 and 1000")
        lines = self.git("log", f"-{limit}", "--format=%H%x09%s").splitlines()
        return [dict(zip(("revision", "message"), line.split("\t", 1))) for line in lines]
