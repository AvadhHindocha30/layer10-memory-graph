# Layer10 Take-Home: Grounded Memory Graph (MVP)

This repo builds a small “enterprise memory” system:
- Ingests a public corpus (GitHub issues/comments JSON)
- Extracts structured entities + claims
- Stores every claim with evidence (grounding)
- Deduplicates claims and handles updates over time
- Builds a queryable memory graph
- Provides a retrieval demo and a visualization UI

## Quickstart (rules mode)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
python3 -m src.generate_context_packs --graph outputs/memory_graph.json --questions examples/questions.json --out outputs/context_packs
python3 -m src.visualize
```

Open the viewer:

```bash
cd outputs
python3 -m http.server 8000
```

Then open:
- http://localhost:8000/memory_graph_view.html

## Docs

- Run instructions: `HowToRun.md`
- Design + approach: `docs/writeup.md`

## Submission snapshot
A ready-to-view snapshot is available in `submission_outputs/`:
- `submission_outputs/memory_graph.json`
- `submission_outputs/context_packs/`
- `submission_outputs/memory_graph_view.html`
