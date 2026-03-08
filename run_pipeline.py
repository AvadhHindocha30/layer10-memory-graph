from __future__ import annotations

from pathlib import Path
import argparse

from src.ingest_demo import ingest_demo_corpus
from src.extract_rules import run_rule_extraction
from src.dedup import run_dedup_and_versioning
from src.extract_llm_ollama import run_llm_extraction


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", default="data/raw/github_corpus.json")
    p.add_argument("--out", default="outputs/memory_graph.json")
    
    p.add_argument("--mode", choices=["rules", "llm"], default="rules")
    p.add_argument("--llm_model", default="llama3.1")

    args = p.parse_args()

    g = ingest_demo_corpus(args.raw)
    if args.mode == "rules":
        g = run_rule_extraction(g)
    else:
        g = run_llm_extraction(g, model=args.llm_model)
    g = run_dedup_and_versioning(g)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(g.to_json(), encoding="utf-8")

    active_claims = sum(1 for c in g.claims.values() if c.status == "active")
    superseded_claims = sum(1 for c in g.claims.values() if c.status == "superseded")

    print("✅ Pipeline complete")
    print(f"- Raw:        {args.raw}")
    print(f"- Artifacts:  {len(g.artifacts)}")
    print(f"- Entities:   {len(g.entities)}")
    print(f"- Claims:     {len(g.claims)} (active={active_claims}, superseded={superseded_claims})")
    print(f"- Evidences:  {len(g.evidences)}")
    print(f"- Wrote:      {out_path}")


if __name__ == "__main__":
    main()