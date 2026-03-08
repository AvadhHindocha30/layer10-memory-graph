# HowToRun (Layer10 Take-Home: Grounded Memory Graph)

This repo builds a grounded “memory graph” from GitHub issues/comments and produces:
- `outputs/memory_graph.json` (entities + claims + evidence + artifacts)
- `outputs/context_packs/` (example retrieval packs)
- `outputs/memory_graph_view.html` (visualization UI)

> Note: Python may create `__pycache__/` when you run code. That’s normal. We don’t commit it to Git.

---

## Quickstart (rules mode, WSL)

From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
python3 -m src.generate_context_packs
python3 -m src.visualize

cd outputs && python3 -m http.server 8000
# open: http://localhost:8000/memory_graph_view.html
```

Stop server: `Ctrl + C`, then:

```bash
cd ..
```

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
python3 -m src.download_github --owner pallets --repo flask --limit 30 --out data/raw/github_corpus.json --token YOUR_TOKEN
```

If you hit `403 rate limit exceeded`, use a GitHub Personal Access Token:
- Create token: GitHub → Settings → Developer settings → Personal access tokens
- Then pass it via `--token`

---

## 3) Build the memory graph (rules mode)

From repo root:

```bash
python3 run_pipeline.py --raw data/raw/github_corpus.json --mode rules
```

Output:
- `outputs/memory_graph.json`

---

## 4) Generate context packs (example retrieval outputs)

From repo root:

```bash
python3 -m src.generate_context_packs
```

Output:
- `outputs/context_packs/q01.json`, `q02.json`, ...

---

## 5) Visualization (generate + open)

### Generate HTML
From repo root:

```bash
python3 -m src.visualize
```

Output:
- `outputs/memory_graph_view.html`

### Open viewer (required: local server)
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

## 6) Retrieval demo (CLI)

From repo root:

```bash
python3 retrieve_demo.py "Which issues mention i18n?"
python3 retrieve_demo.py "Who authored #5817?"
python3 retrieve_demo.py "Which issues did aw0imbee comment on?"
```

---

## 7) LLM extraction mode (Ollama) — install + download model (4–5GB)

This mode uses a **local free model** via Ollama.
The model download is typically **~4–5 GB** (the big download you saw).

### A) Install Ollama (Windows)
1) Download Ollama from: https://ollama.com/download
2) Install it (default install path is fine)

### B) Download the model (Windows PowerShell)
Open **Windows PowerShell** and run:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull llama3.1
```

Wait until it says `success`.

### C) Ensure the Ollama server is running
Usually Ollama runs in the background automatically after install.
If API calls fail, start it manually:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

If you see “port already in use / only one usage of each socket”, that usually means it’s **already running** — that’s fine.

Optional quick check (PowerShell):

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

---

## 8) Run pipeline in LLM mode (recommended way)

Because Ollama runs on **Windows** (localhost:11434), the most reliable approach is:

### Run LLM pipeline from Windows PowerShell (repo root)
Go to your repo folder in PowerShell (the same folder that contains `run_pipeline.py`), then run:

```powershell
python run_pipeline.py --raw data/raw/github_corpus.json --mode llm --llm_model llama3.1
```

This updates:
- `outputs/memory_graph.json`

If it times out once, re-run it (first request can be slow while the model warms up).

### Refresh packs + viewer (WSL or PowerShell)
After LLM mode, regenerate context packs + viewer:

```bash
python3 -m src.generate_context_packs
python3 -m src.visualize
cd outputs && python3 -m http.server 8000
```

Open:
- http://localhost:8000/memory_graph_view.html

Stop server: `Ctrl + C`, then:

```bash
cd ..
```
