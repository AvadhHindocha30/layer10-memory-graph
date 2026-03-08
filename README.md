# Layer10 Take-Home: Grounded Memory Graph (MVP)

This repo builds a small “enterprise memory” system:
- Ingests a public corpus (GitHub issues + comments JSON)
- Extracts structured **entities + claims**
- Stores every claim with **grounded evidence**
- Deduplicates repeated claims and supports time evolution via `active` / `superseded`
- Builds a queryable memory graph
- Produces **context packs** (retrieval with evidence)
- Provides a lightweight visualization

---

## Repo layout

- `data/raw/github_corpus.json` — downloaded GitHub snapshot (issues + comments)
- `src/` — ingestion, extraction, dedup, context pack generator, visualization generator
- `outputs/memory_graph.json` — serialized memory graph (entities/claims/evidence/artifacts)
- `outputs/context_packs/` — example retrieval outputs (`q01.json ... q05.json`)
- `outputs/memory_graph_view.html` — viewer UI (serve locally)

---

## Quickstart (WSL/Linux) — rules mode (fast, no Ollama)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
python3 -m src.generate_context_packs
python3 -m src.visualize

cd outputs
python3 -m http.server 8000
# open: http://localhost:8000/memory_graph_view.html