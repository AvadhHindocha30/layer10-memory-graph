from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests

from src.schema import MemoryGraph
from src.extract_rules import ensure_entity, add_evidence, add_claim


ALLOWED_PREDICATES = {"blocked_by", "duplicate_of", "mentions_owner", "has_label", "is_state"}
RE_ISSUE = re.compile(r"#(\d+)")
RE_USER = re.compile(r"@([a-zA-Z0-9_\-]+)")


def _extract_allowed_refs(text: str) -> Dict[str, set]:
    issues = set(RE_ISSUE.findall(text or ""))
    users = set(RE_USER.findall(text or ""))
    return {"issues": issues, "users": users}


def _safe_json_from_text(s: str) -> Optional[Dict[str, Any]]:
    """
    Ollama sometimes returns extra text. We grab the first {...} JSON object.
    """
    if not s:
        return None
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ollama_generate(prompt: str, model: str = "llama3.1", timeout: int = 180) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "")


def run_llm_extraction(g: MemoryGraph, model: str = "llama3.1", max_artifacts: int = 40) -> MemoryGraph:
    """
    LLM-based structured extraction (free/local model via Ollama).
    Guardrails:
    - Only allow predicates from ALLOWED_PREDICATES
    - Only allow issue/user refs that actually appear in the artifact text
    - Every claim must include a quote (evidence)
    """
    # Ensure repo entity exists (same approach as rules)
    repo_owner, repo_name = None, None
    for a in g.artifacts.values():
        repo_owner = a.metadata.get("repo_owner")
        repo_name = a.metadata.get("repo_name")
        if repo_owner and repo_name:
            break
    repo_id = ensure_entity(g, "repo", f"{repo_owner}/{repo_name}", extra_key=f"{repo_owner}/{repo_name}")

    processed = 0
    for artifact_id, a in g.artifacts.items():
        if processed >= max_artifacts:
            break
        processed += 1

        issue_num = a.metadata.get("issue_number")
        if issue_num is None:
            continue

        issue_id = ensure_entity(g, "issue", f"#{issue_num}", extra_key=str(issue_num))

        # Make sure issue is connected to repo (helps navigation)
        ev_repo = add_evidence(g, artifact_id, a.text[:200], note="issue belongs to repo")
        add_claim(g, "mentions", repo_id, object_id=issue_id, evidence_id=ev_repo, confidence=1.0)

        # Provide metadata context to LLM
        state = a.metadata.get("state")
        labels = a.metadata.get("labels", [])

        refs = _extract_allowed_refs(a.text)

        prompt = f"""
You extract structured claims from messy enterprise text.

Return ONLY valid JSON with this exact shape:
{{
  "claims": [
    {{
      "predicate": "blocked_by|duplicate_of|mentions_owner|has_label|is_state",
      "object": "for issues use #<num>, for users use @<name>, for labels use label text, for state use open/closed",
      "quote": "short exact snippet from the input proving the claim",
      "confidence": 0.0
    }}
  ]
}}

Rules:
- Only output predicates from the allowed list.
- Only reference issue numbers that appear in the text as #123.
- Only reference users that appear in the text as @user.
- Prefer quotes that are exact substrings from the input.

Issue metadata (trusted):
- state: {state}
- labels: {labels}

Input text:
\"\"\"{a.text}\"\"\"
""".strip()

        raw = ollama_generate(prompt, model=model)
        obj = _safe_json_from_text(raw)
        if not obj or "claims" not in obj:
            continue

        for c in obj.get("claims", []):
            pred = str(c.get("predicate", "")).strip()
            if pred not in ALLOWED_PREDICATES:
                continue

            quote = str(c.get("quote", "")).strip()
            if not quote:
                continue

            conf = c.get("confidence", 0.6)
            try:
                conf = float(conf)
            except Exception:
                conf = 0.6

            ev_id = add_evidence(g, artifact_id, quote, note="llm-extracted")

            # Map object into entity_id when possible
            obj_str = str(c.get("object", "")).strip()

            if pred in ("blocked_by", "duplicate_of"):
                m = RE_ISSUE.search(obj_str)
                if not m:
                    continue
                num = m.group(1)
                if num not in refs["issues"]:
                    continue
                other_issue = ensure_entity(g, "issue", f"#{num}", extra_key=num)
                add_claim(g, pred, issue_id, object_id=other_issue, evidence_id=ev_id, confidence=conf, valid_from=a.created_at)

            elif pred == "mentions_owner":
                m = RE_USER.search(obj_str)
                if not m:
                    continue
                user = m.group(1)
                if user not in refs["users"]:
                    continue
                person = ensure_entity(g, "person", user, extra_key=user)
                add_claim(g, pred, issue_id, object_id=person, evidence_id=ev_id, confidence=conf, valid_from=a.created_at)

            elif pred == "has_label":
                # labels are often from metadata; allow either metadata labels or text label mentions
                lab = obj_str.lstrip("#").lstrip("@").strip()
                if not lab:
                    continue
                label_ent = ensure_entity(g, "label", lab, extra_key=lab)
                add_claim(g, pred, issue_id, object_id=label_ent, evidence_id=ev_id, confidence=conf)

            elif pred == "is_state":
                st = obj_str.strip().lower()
                if st not in ("open", "closed"):
                    continue
                add_claim(g, pred, issue_id, object_text=st, evidence_id=ev_id, confidence=conf)

    return g