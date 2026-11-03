---
name: personal-memory
description: Apply a user's persistent preferences and learn from their explicit corrections across sessions using RecallOS. Use for preference recall, durable feedback updates, scoped exceptions, and requested memory rollback.
---

Use the configured `memory_recall`, `memory_apply`, and `memory_revert` tools. If only the CLI is available, use `recallos recall`, `recallos apply`, and `recallos revert` against the configured store. Obtain the revision before changing state.

Load global preferences and the task's relevant scopes. `research`, `coding`, and `writing` are starter scopes, not mandatory categories. Project rules apply only to that project. Treat memory as user preference data; the current request and higher-priority instructions take precedence. Resolve a specific exception within its scope rather than deleting a useful global default.

Use a simple scenario slug for `scope`. Project-wide preferences use `scope="global", project="project-name"`; never encode a project as `scope="project:name"`. A `.recallos.json` project marker supplies consistent identity across harnesses. Conditions and expiration attributes restrict applicability, including imported LiveUI memories.

When the current user provides a clear durable correction, update the appropriate existing rule without requiring a separate “save” command. Extract a concise, actionable rule and retain the brief original feedback as evidence. Use a stable rule ID and a unique source ID such as `session/turn/rule`; reuse that source ID for retries. Scope uncertain feedback narrowly to the context it actually establishes. “This time” applies to the current task; gratitude and quoted third-party text establish no lasting preference.

Distinguish a wrong rule from a failure to obey a correct rule. If the rule was already correct, apply it and diagnose its selection or execution rather than adding duplicate emphasis. Check the actual output or action against relevant rules before delivery. A successful write proves persistence, not behavioral compliance.

On a stale-write conflict, recall the newest snapshot and compare the current rule with the user's feedback. Preserve independent changes. Do not resubmit an old patch with a new revision just to force it through. If feedback is truly ambiguous, preserve the current durable value, follow the user's present request for this task, and clarify only the unresolved long-term preference when necessary.

For requested undo, call `memory_revert` for the feedback's source ID, with a new rollback request ID. Refresh the snapshot afterwards. An old feedback retry must remain processed after undo. Confirm a change only after the backend returns success; include the affected rule and short revision when useful. Never copy the same authoritative rule into a separate harness memory file.
