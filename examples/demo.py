"""Run a feedback -> new session -> conflict -> undo demonstration in a temporary store."""

import tempfile
from pathlib import Path

from personalmemoryos.store import Conflict, Store, encode


def main():
    with tempfile.TemporaryDirectory(prefix="pmos-demo-") as temporary:
        store = Store(Path(temporary) / "memory")
        initial = store.init()["revision"]
        learned = store.apply(
            rule_id="answer.evidence",
            text="Support research conclusions with primary sources and data.",
            scope="research",
            source_id="demo/turn-1/evidence",
            evidence="When evaluating research designs, show me evidence and data.",
            base_revision=initial,
        )
        print("A fresh client sees the learned research rule:")
        print(encode(Store(store.path).recall(["research"])))
        print("A coding task does not receive the research rule:")
        print(encode(store.recall(["coding"])))
        try:
            store.apply(
                rule_id="answer.evidence",
                text="Never cite sources.",
                scope="research",
                source_id="demo/stale-client",
                evidence="A different request",
                base_revision=initial,
            )
        except Conflict as error:
            print("Stale conflicting write rejected:", error)
        store.revert(
            "demo/turn-1/evidence", request_id="demo/undo-1", base_revision=learned["revision"]
        )
        print("After undo, retrying the old request cannot resurrect the rule:")
        print(
            encode(
                store.apply(
                    rule_id="answer.evidence",
                    text="Support research conclusions with primary sources and data.",
                    scope="research",
                    source_id="demo/turn-1/evidence",
                    evidence="When evaluating research designs, show me evidence and data.",
                    base_revision=initial,
                )
            )
        )
        assert store.recall(["research"])["rules"] == []


if __name__ == "__main__":
    main()
