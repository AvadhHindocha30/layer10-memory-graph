# HowToRun (Layer10 Take-Home: Grounded Memory Graph)

This repo builds a grounded “memory graph” from GitHub issues/comments and produces:
- `outputs/memory_graph.json` (entities + claims + evidence + artifacts)
- `outputs/context_packs/` (example retrieval packs)
- `outputs/memory_graph_view.html` (visualization UI)

> Note: Python may create `__pycache__/` when you run code. That’s normal. We do not commit it to Git.

---

## 1) Setup (WSL / Linux)

From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2) Dataset

### Option A (recommended): use the included dataset
This repo already contains:
- `data/raw/github_corpus.json`

So you can skip downloading.

### Option B: download a fresh dataset (may require GitHub token due to rate limits)

```bash
python3 -m src.download_github --owner pallets --repo flask --limit 30 --out data/raw/github_corpus.json
```

If you hit `403 rate limit exceeded`, use a GitHub Personal Access Token:

- Create token: GitHub → Settings → Developer settings → Personal access tokens
- Then pass it via `--token`

Example with token:

```bash
python3 -m src.download_github --owner pallets --repo flask --limit 30 --out data/raw/github_corpus.json --token YOUR_TOKEN
```

---

## 3) Build the memory graph (rules mode)

From repo root:

```bash
python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
```

Output:
- `outputs/memory_graph.json`

---

## 4) Generate context packs

From repo root:

```bash
python3 -m src.generate_context_packs --graph outputs/memory_graph.json --questions examples/questions.json --out outputs/context_packs
```

Output:
- `outputs/context_packs/*.json`

---

## 5) Generate the visualization HTML

From repo root:

```bash
python3 -m src.visualize
```

Output:
- `outputs/memory_graph_view.html`

---

## 6) Open viewer (required: local server)

The HTML uses `fetch("memory_graph.json")`, which browsers block if you open via `file://`.

From repo root:

```bash
cd outputs
python3 -m http.server 8000
```

Open in browser:
- http://localhost:8000/memory_graph_view.html

Stop server:
- `Ctrl + C`

Go back to repo root:
```bash
cd ..
```

---

## 7) Retrieval demo (CLI)

From repo root:

```bash
python3 retrieve_demo.py "Who authored #5817?"
python3 retrieve_demo.py "Which issues did nitin-999-code comment on?"
python3 retrieve_demo.py "What labels does #5836 have?"
```

---

## 8) LLM extraction mode (Ollama) — Install + run

This mode uses a **local free model** via Ollama.
The model download can be **~4–5 GB**.

### A) Install Ollama (Windows)
1) Download from: https://ollama.com/download
2) Install it

### B) Download model (Windows PowerShell)

```powershell
ollama pull llama3.1
```

### C) Start the Ollama server (Windows PowerShell)

```powershell
ollama serve
```

Keep this terminal open while running LLM mode.

### D) Run pipeline in LLM mode

**Important (WSL users):** if Ollama is running on **Windows**, the simplest is to run the pipeline in **Windows PowerShell** (same machine) so `http://localhost:11434` works.

From the repo root (PowerShell):

```powershell
py run_pipeline.py --raw data/raw/github_corpus.json --mode llm --llm_model llama3.1
```

Then regenerate context packs + viewer (PowerShell or WSL):

```bash
python3 -m src.generate_context_packs --graph outputs/memory_graph.json --questions examples/questions.json --out outputs/context_packs
python3 -m src.visualize
```

Open the viewer again (Section 6).

---

## 9) One-shot (rules) to refresh everything

From repo root:

```bash
python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
python3 -m src.generate_context_packs --graph outputs/memory_graph.json --questions examples/questions.json --out outputs/context_packs
python3 -m src.visualize
```
