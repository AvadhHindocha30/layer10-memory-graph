from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple


def load_graph(path: str = "outputs/memory_graph.json") -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    return re.findall(r"[a-z0-9_#]+", s)


def claim_text(graph: Dict[str, Any], claim: Dict[str, Any]) -> str:
    ents = graph["entities"]

    subj = ents.get(claim["subject_id"], {}).get("name", claim["subject_id"])
    if claim.get("object_id"):
        obj = ents.get(claim["object_id"], {}).get("name", claim["object_id"])
    else:
        obj = claim.get("object_text", "")

    # IMPORTANT: scoring should be based on structured fields ONLY
    return " ".join([claim["predicate"], str(subj), str(obj)])


def score_claim(q_tokens: List[str], text: str) -> int:
    t = text.lower()
    score = 0
    for w in q_tokens:
        if w in t:
            score += 2
    return score


def answer(question: str, top_k: int = 5) -> None:
    graph = load_graph()
    claims = list(graph["claims"].values())

    q_tokens = tokenize(question)
    scored: List[Tuple[int, Dict[str, Any]]] = []

    for c in claims:
        if c.get("status") != "active":
            continue
        t = claim_text(graph, c)
        s = score_claim(q_tokens, t)
        if s > 0:
            scored.append((s, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[:top_k]

    print("\n=== Question ===")
    print(question)

    if not best:
        print("\nNo strong matches found in memory graph.")
        print("Tip: try including issue numbers like #101 or words like 'blocked', 'owner', 'label'.")
        return

    ents = graph["entities"]
    evs = graph["evidences"]
    arts = graph["artifacts"]

    print("\n=== Top evidence-backed claims ===")
    for rank, (s, c) in enumerate(best, 1):
        subj = ents.get(c["subject_id"], {}).get("name", c["subject_id"])
        obj = c.get("object_text")
        if c.get("object_id"):
            obj = ents.get(c["object_id"], {}).get("name", c["object_id"])

        print(f"\n[{rank}] score={s}  {c['predicate']}({subj} -> {obj})")
        print(f"    confidence={c.get('confidence')}  valid_from={c.get('valid_from','')}")

        for ev_id in c.get("evidence_ids", [])[:2]:
            ev = evs.get(ev_id, {})
            art = arts.get(ev.get("artifact_id", ""), {})
            author = art.get("author", "")
            kind = art.get("metadata", {}).get("kind", "")
            print(f"    - evidence (author={author}, kind={kind}): {ev.get('quote','')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 retrieve_demo.py \"your question here\"")
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    answer(question)


if __name__ == "__main__":
    main()