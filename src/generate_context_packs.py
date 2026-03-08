from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re

from src.schema import MemoryGraph


def tokenize(s: str) -> List[str]:
    return re.findall(r"[a-z0-9_#]+", (s or "").lower())


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


def build_context_pack(graph: Dict[str, Any], question: str, top_k: int = 5) -> Dict[str, Any]:
    q_tokens = tokenize(question)
    claims = list(graph["claims"].values())

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for c in claims:
        if c.get("status") != "active":
            continue
        s = score_claim(q_tokens, claim_text(graph, c))
        if s > 0:
            scored.append((s, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[:top_k]

    ents = graph["entities"]
    evs = graph["evidences"]
    arts = graph["artifacts"]

    results = []
    for s, c in best:
        subj = ents.get(c["subject_id"], {}).get("name", c["subject_id"])
        if c.get("object_id"):
            obj = ents.get(c["object_id"], {}).get("name", c["object_id"])
        else:
            obj = c.get("object_text", "")

        evidences = []
        for ev_id in c.get("evidence_ids", [])[:2]:
            ev = evs.get(ev_id, {})
            art = arts.get(ev.get("artifact_id", ""), {})
            evidences.append({
                "evidence_id": ev_id,
                "quote": ev.get("quote", ""),
                "artifact_id": ev.get("artifact_id", ""),
                "artifact_author": art.get("author", ""),
                "artifact_kind": (art.get("metadata") or {}).get("kind", ""),
                "artifact_created_at": art.get("created_at", ""),
                "artifact_url": art.get("url", ""),
            })

        results.append({
            "score": s,
            "predicate": c.get("predicate"),
            "subject": subj,
            "object": obj,
            "confidence": c.get("confidence"),
            "valid_from": c.get("valid_from"),
            "evidence": evidences,
        })

    return {
        "question": question,
        "top_k": top_k,
        "results": results,
    }


def main():
    cfg = json.loads(Path("examples/questions.json").read_text(encoding="utf-8"))
    graph_path = Path("outputs/memory_graph.json")
    if not graph_path.exists():
        raise FileNotFoundError("outputs/memory_graph.json not found. Run pipeline first: python3 run_pipeline.py --raw ...")

    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    out_dir = Path("outputs/context_packs")
    out_dir.mkdir(parents=True, exist_ok=True)

    questions = cfg.get("questions", [])
    for i, q in enumerate(questions, 1):
        pack = build_context_pack(graph, q, top_k=5)
        out_file = out_dir / f"q{i:02d}.json"
        out_file.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ wrote {out_file}")

    print("Done. Context packs are in outputs/context_packs/.")


if __name__ == "__main__":
    main()