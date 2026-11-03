# Evidence behind the design

Reviewed 2026-11-03. These sources motivate the design; their reported results are **not PersonalMemoryOS benchmarks**. None proves that this implementation, every model, or every user will improve monotonically.

## Corrective feedback can improve later tasks

[PAHF: Learning Personalized Agents from Human Feedback](https://arxiv.org/html/2602.16173v1) studies explicit per-user memory updated from pre-action clarification and post-action corrections. Its shopping evaluation reports the following in Table 1; evaluation phases do not provide new feedback:

| Method | After initial learning | After preference drift and relearning |
|---|---:|---:|
| No memory | 27.8% | 27.0% |
| Pre-action only | 34.4% | 56.0% |
| Post-action only | 38.9% | 66.9% |
| Both | 41.3% | 70.3% |

This supports a correction → update → later-task-use loop. It uses simulated users and bounded domains; it does not validate this project's inference, Git logic, or general chat compliance. Use the table's phase-specific values; one nearby prose passage inconsistently labels phase results.

## Retained state can help across fresh episodes

[PAST-Bench](https://arxiv.org/html/2608.04003v1) compares persistent-state access under matched prompts, tools, graders, and seeds. Its Hermes/GPT-5.4 comparison reports overall score 0.51 without retained state versus 0.75 with it, and Update score 0.46 versus 0.80. The authors call this a strong design control, not strict causal proof. These are constructed-task aggregate scores, not everyday user success rates.

## Remembering does not establish correct application

[MemPABench](https://arxiv.org/html/2610.30485v1), October 2026, evaluates interaction preferences across simulated sessions. File memory improves preference selection from 49.6% to 59.2%, while also increasing inappropriate cross-context carry-over. Retrieval-based conditions in that setup show little aggregate improvement. This motivates scope, explicit exceptions, and checking actual behavior rather than only retrieval accuracy.

## Production architecture examples

- [Claude Code memory](https://code.claude.com/docs/en/memory): a short `MEMORY.md` index plus separately loaded memory files, with preferences and corrective feedback as intended inputs. Imports alone do not reduce context usage when all imported content is loaded.
- [Letta MemFS](https://docs.letta.com/concepts/memfs): Markdown memory in Git, a distinction between resident and on-demand content, and ordinary file tools. [Context Repositories](https://www.letta.com/blog/context-repositories/) describes versioned changes and concurrent reflection in worktrees. This project chooses a single local writer for a smaller implementation.
- [Mem0's Strands integration](https://docs.mem0.ai/integrations/strands): a memory manager drives automatic recall and optional extraction in the agent loop. It illustrates why host lifecycle integration matters; exposing tools alone does not ensure that models invoke them.

These examples establish implementable patterns. Product documentation and vendor case studies alone do not establish controlled gains for this project.

## What remains to measure here

The repository tests storage and protocol invariants. Actual preference adherence, quality of automatic scope selection, correctness of feedback extraction, and cross-model behavior need [fresh-session behavioral experiments](evaluation.md). No published percentage is used as this project's own performance claim.
