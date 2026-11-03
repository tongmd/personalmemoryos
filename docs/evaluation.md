# Behavioral evaluation protocol

Storage correctness and model compliance are separate outcomes. The included unit tests cover the former. This document specifies a small reproducible experiment for the latter; it is not a claim that the experiment has been run.

Compare three conditions with the same model/harness configuration:

1. No persistent memory.
2. A fixed initial memory snapshot, without feedback updates.
3. The same initial snapshot, with feedback updates enabled.

Use synthetic or explicitly chosen non-sensitive preferences. Keep training corrections separate from held-out task prompts. Start a fresh session for each held-out task so previous conversation context cannot explain an improvement.

For each important correction, create an applicable example and a counterexample where it must not apply. Include global defaults, scenario exceptions, project isolation, temporary instructions, preference changes, and rollback. Inspect whether the host actually selected the expected revision and rule IDs before judging the output.

Suggested records:

```json
{"case":"research-evidence-1","scope":"research","prompt":"Evaluate these two approaches","expected_rule":"answer.evidence","expected_behavior":"Provide primary sources and data supporting the comparison","must_not":"Invent references","training_feedback":"For research evaluations, show me evidence and data."}
```

Record the harness and model version, configuration, commit revision, selected rule IDs, request, relevant tool calls, output, elapsed time, and scoring rubric. Use deterministic checks where possible; for semantic criteria use a fixed rubric with blinded human review or an independently assessed judge. Avoid judging only whether the model repeats the preference.

Report:

- Correct application rate on held-out relevant tasks.
- Inappropriate application rate on counterexamples.
- Recurrence of the same error after feedback.
- Number of corrections needed after preference drift.
- Added latency and context size.
- Results separated by harness and task type.

Treat small differences cautiously and repeat enough cases to report uncertainty. A change that improves relevant tasks while increasing cross-context mistakes needs a narrower scope, not a larger memory file. Any future automated promotion gate should evaluate both new examples and existing held-out cases before claiming an improvement.
