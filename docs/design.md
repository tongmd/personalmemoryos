# State model and consistency contract

## What is authoritative

A dedicated Git repository contains active Markdown rules and an append-only event ledger. The public application repository and private memory repository are separate. `MEMORY.md` is generated navigation; each rule file is authoritative for that scoped rule. No SQLite mirror or independently writable harness copy exists.

Rule identity is `(project, scope, rule_id)`. A global rule and a research exception may share a stable rule ID while remaining distinct records. Project-specific records never enter another project's snapshot. Different scenario rules may coexist; the agent must resolve applicability from the task. The storage layer does not detect arbitrary semantic contradictions between differently named IDs.

Each rule has JSON frontmatter for machine-readable metadata and ordinary Markdown text for its actionable preference. JSON avoids requiring a YAML dependency while remaining valid YAML. Rule and project identifiers are restricted slugs; text and evidence have bounded lengths.

## Feedback transition

1. The host interprets the user's current correction and selects an existing rule ID/scope when appropriate.
2. It sends a patch with its observed `base_revision`, a unique `source_id`, brief evidence, and replacement text (or null for forgetting).
3. The store takes a local exclusive process lock, checks a clean worktree, and deduplicates the source ID.
4. It compares the target rule in the base commit with the current commit. An unchanged target may be patched despite unrelated intervening commits. An identical desired value is recorded without rewriting the rule. A changed target with a different value raises a conflict.
5. It commits the changed rule, a feedback receipt, and regenerated navigation together.

No change occurs for a rejected conflict. The source ID is recorded only on a successful commit. Retrying an identical processed request returns `already_processed`, even if the associated rule has since been undone. A changed payload under the same ID is rejected.

### Example: narrowing a preference

Existing global `answer.length`: “Keep answers concise.”

Feedback: “For research design reviews, explain the evidence in detail.”

Create a research-scoped `answer.length` exception. Preserve the global rule. A later coding task loads only the concise default. “This time explain everything” stays in the current task and causes no persistent write.

### Example: independent concurrent patches

Codex and Claude read revision A. Codex writes a language preference and creates B. Claude's patch changes a testing rule untouched since A. The store applies it to B and commits C; neither update is lost.

If both clients change the same scoped rule to different values, the second patch conflicts. The agent must inspect the newest rule and feedback provenance. Last network arrival does not establish which user correction is newer.

## Snapshot isolation and hot reload

`recall` captures one commit and reads every selected rule through Git object reads. A writer may be editing working files, but the reader sees either the old or new commit, never a mixed tree. A hook invocation on the next user turn captures the new revision. Historical snapshot reads are supported for ancestor commit hashes.

Updates do not retroactively edit a model's in-flight context. Old snapshots can still be present in its conversation; the new wrapper explicitly supersedes them within the selected scopes. A model's compliance with that instruction must be evaluated. Restarting a model turn or using a deterministic action checker can provide stronger behavior for particular requirements; this package does not claim universal enforcement.

## Rollback without resurrection

Undo is a compensating commit restoring the affected rule's previous contents. It retains the original feedback receipt and adds an undo receipt. It is intentionally not a raw `git revert` of the entire feedback commit, because that would remove the receipt used for deduplication.

If the rule has been edited since the target feedback, undo returns a conflict rather than removing the later change. Other rules are left intact. A new request ID makes the undo operation itself retry-safe. To intentionally reintroduce an undone preference, send new user feedback with a new source ID.

Do not hard-reset the live store or manually remove its event receipts: this bypasses the anti-resurrection contract. Inspect snapshots and diffs with normal Git tools. This release provides targeted feedback undo, not arbitrary full-history restoration or history redaction.

## Failure model

All local writers must use this API and the same store path. The lock is for one host, not a distributed lock for network filesystems or divergent clones. External manual writes are rejected while the worktree is dirty; review and commit or restore them before API writes. Direct committed edits remain inspectable but have no automatic feedback receipt.

Handled commit failures restore the pre-write files and index paths. A killed process or machine crash can leave an uncommitted worktree; later writes refuse to proceed rather than overwrite it. Readers continue to use the last complete commit. Inspect `git status` and the diff before explicitly recovering. There is no automatic push or background history replay.

Full user conversations are not ingested. Only the short supplied evidence is stored; Git history retains prior evidence. The library cannot verify that a malicious or mistaken harness accurately attributed that evidence. It is intended for trusted local agents acting on the user's instructions.
