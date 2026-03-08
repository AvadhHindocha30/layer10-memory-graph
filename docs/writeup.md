# Layer10 Take-Home: Grounded Memory Graph (MVP)

## 0) What this project is
This repo implements a minimal, production-inspired **grounded memory system** for messy enterprise-style discussions.

Given a corpus of GitHub issues + comments (text + metadata), the pipeline:
1) ingests raw items as immutable **Artifacts**
2) extracts structured **Entities** and typed **Claims**
3) requires that every Claim has supporting **Evidence** (grounding)
4) deduplicates / versions “latest truth” claims over time (active vs superseded)
5) supports retrieval (Q&A) that returns **evidence-backed** answers
6) provides a lightweight visualization to inspect the memory graph

Outputs are written to `outputs/` so a reviewer can inspect without re-running everything.

---

## 1) Dataset
### Corpus format
Input is a JSON file containing:
- repository metadata (`owner`, `name`)
- `items[]` where each item is an issue with:
  - issue number, title, body, state, labels, author, created_at, url
  - comments[] where each comment has text, author, created_at

Main file used:
- `data/raw/github_corpus.json`

Downloader (optional, reproducible):
- `src/download_github.py`

Why GitHub?
- It mixes structured signals (labels/state) with unstructured discussion.
- It contains real “enterprise-like” edge cases: references to other issues (`#123`), duplicates, blockers, assignment/ownership, and long comment threads.

---

## 2) Core data model (Schema / Ontology)
Defined in `src/schema.py`. The system is intentionally explicit and audit-friendly.

### 2.1 Artifacts (immutable ground truth)
Artifacts are the raw source objects:
- issue text (title + body)
- comment text

Each Artifact stores:
- stable `artifact_id`
- source fields (author, created_at, url)
- text
- metadata (repo, issue_number, kind=issue/comment, etc.)

Artifacts are treated as immutable so every later extraction can point back to a stable source-of-truth.

### 2.2 Evidence (grounding)
Evidence objects connect claims to artifacts:
- `artifact_id`
- `quote` (short excerpt shown in UI + retrieval output)
- optional offsets (start_char/end_char when found)

**Rule:** every Claim must include one or more `evidence_ids`.
This prevents “floating facts” and makes auditing straightforward.

### 2.3 Entities
Entities are canonical nodes in the memory graph:
- `repo`
- `issue`
- `person`
- `label`

Entities have stable IDs and canonical names (so different mentions map to the same node).

### 2.4 Claims (typed edges)
Claims represent structured facts/relationships. Examples in this repo:
- `mentions(repo -> issue)`
- `is_state(issue -> open/closed)`
- `has_label(issue -> label)`
- `blocked_by(issue -> issue)`
- `duplicate_of(issue -> issue)`
- `mentions_owner(issue -> person)` (assignment/ownership mention)
- `authored_issue(issue -> person)` (from issue metadata)
- `commented_on(issue -> person)` (from comment metadata)

Each Claim includes:
- `predicate` (type)
- subject/object (entity IDs, or object_text for literals)
- `confidence`
- `status` ∈ {`active`, `superseded`}
- optional `valid_from`, `valid_to`
- `evidence_ids[]`

---

## 3) Pipeline architecture
The pipeline is implemented as a few clear stages so it is easy to debug and extend.

### 3.1 Ingestion
File: `src/ingest_demo.py`

Ingestion converts raw JSON into Artifacts and also creates basic entity/claim structure that is guaranteed grounded:
- repo entity
- issue entities
- person entities (authors / commenters)
- claims like `authored_issue` and `commented_on`
- evidence quotes such as `author: <name>` or `commenter: <name>`

This ensures “person” nodes are connected even if the text itself does not mention `@username` patterns.

### 3.2 Extraction (two modes)
The system supports two extraction modes chosen by `run_pipeline.py`:

#### A) Rule-based extraction (deterministic)
File: `src/extract_rules.py`

Uses regex + heuristics for high-precision patterns:
- issue references like `#123`
- “blocked by #123”, “duplicate of #123”
- label/state from metadata (and optionally from text)
- ownership/assignment phrases (heuristic)

For every extracted fact:
- create/lookup entities
- create claim
- create evidence quote pointing to the correct artifact

This mode is reliable and fully auditable.

#### B) LLM extraction (optional enhancement)
File: `src/extract_llm_ollama.py`

Uses a local LLM (Ollama) to extract additional structured facts from messy text.
It still enforces:
- schema constraints
- evidence requirement (must attach evidence quotes)
- conservative confidence defaults

Why optional?
- The core assignment can be satisfied with deterministic extraction.
- LLM mode is an additional capability to show how the architecture extends to agentic/LLM workflows.

### 3.3 Deduplication + time evolution
File: `src/dedup.py`

Some predicates represent “latest truth” (e.g., current owner/state). The dedup/versioning step:
- groups claims by (predicate, subject)
- keeps the latest/most-relevant as `active`
- marks earlier contradictory values as `superseded`

This preserves history for audit while making retrieval prefer current truth.

### 3.4 Graph serialization
File: `run_pipeline.py`

Writes:
- `outputs/memory_graph.json`

The JSON includes:
- entities, artifacts, evidences, claims
- merge_log (reserved for future entity merge audit trail)

---

## 4) Retrieval and context packs
### 4.1 Retrieval demo (CLI)
File: `retrieve_demo.py`

Given a natural language question, the script:
- tokenizes the question
- scores claims using lightweight keyword overlap (predicate + entity names + evidence quotes)
- prints the top evidence-backed claims with their supporting evidence

This is intentionally minimal. In production this would likely be:
- embedding retrieval over evidence and/or claim text
- reranking (cross-encoder / LLM judge)
- guardrails (confidence thresholds, citation completeness)

### 4.2 Context packs
File: `src/generate_context_packs.py`

Reads a small question set from `examples/questions.json` and writes:
- `outputs/context_packs/q01.json`, ...

Each context pack contains:
- the question
- top matching claims (prefer active)
- the evidence excerpts and artifact metadata
This is a useful artifact for evaluation and for feeding downstream LLM agents.

---

## 5) Visualization
File: `src/visualize.py` → generates `outputs/memory_graph_view.html`

The viewer is a static HTML page that loads `outputs/memory_graph.json` and supports:
- entity selection
- incoming/outgoing connected claims
- evidence display under each claim
- a small ego-graph around the selected entity (SVG, no external JS libs)

It is designed to be reproducible and easy for a reviewer to open locally:
- `cd outputs && python3 -m http.server 8000`
- open `http://localhost:8000/memory_graph_view.html`

---

## 6) Reliability notes (guardrails mindset)
Even in this MVP, the design follows reliability principles Layer10 cares about:
- **Grounding is mandatory:** every claim has evidence.
- **Auditability:** artifacts are immutable, claims preserve history via status/versioning.
- **Deterministic-first:** rule extractor provides a high-precision baseline.
- **LLM as augmentation:** LLM extraction is constrained by schema + evidence requirements.
- **Clear failure modes:** if nothing matches a query, retrieval returns “no strong matches” instead of hallucinating.

---

## 7) How this generalizes to enterprise workflows
In Layer10-style deployments:
- Artifacts = Slack messages, emails, tickets, call transcripts, docs
- Rules capture obvious structured signals (IDs, assignments, statuses)
- LLM handles messy language and edge cases
- Dedup/versioning tracks evolving truth (status changes, reassignments)
- Retrieval returns evidence-backed answers (citations) for trust and compliance

The same core architecture applies: **Artifacts → Evidence-backed Claims → Versioned Memory Graph → Retrieval + UI**.

---

## 8) Repo outputs (what to inspect)
- `outputs/memory_graph.json` → serialized memory graph
- `outputs/context_packs/` → example retrieval packs
- `outputs/memory_graph_view.html` → viewer UI (serve via local http server)

See `HowToRun.md` for exact commands.
