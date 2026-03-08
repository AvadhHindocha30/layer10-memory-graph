from __future__ import annotations

import re
from typing import Tuple, Optional, List

from src.schema import MemoryGraph, Entity, Claim, Evidence, stable_id


RE_ISSUE_REF = re.compile(r"#(\d+)")
RE_USER_MENTION = re.compile(r"@([a-zA-Z0-9_\-]+)")


def canonical_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def ensure_entity(g: MemoryGraph, entity_type: str, name: str, *, extra_key: Optional[str] = None) -> str:
    """
    Create or return an entity id for (type, name).
    stable_id makes it deterministic for dedup.
    """
    canon = canonical_name(name)
    key = extra_key if extra_key is not None else canon
    eid = stable_id(entity_type, key)

    if eid not in g.entities:
        g.entities[eid] = Entity(
            entity_id=eid,
            entity_type=entity_type,   # type: ignore
            name=name,
            canonical_name=canon,
            aliases=[],
            metadata={},
        )
    return eid


def add_evidence(g: MemoryGraph, artifact_id: str, quote: str, note: Optional[str] = None) -> str:
    quote_clean = " ".join((quote or "").strip().split())

    # try to find offsets inside the artifact text
    start_char = None
    end_char = None
    art = g.artifacts.get(artifact_id)
    if art and quote_clean:
        idx = art.text.find(quote_clean)
        if idx != -1:
            start_char = idx
            end_char = idx + len(quote_clean)

    ev_id = stable_id("evidence", artifact_id, quote_clean[:120])
    if ev_id not in g.evidences:
        g.evidences[ev_id] = Evidence(
            evidence_id=ev_id,
            artifact_id=artifact_id,
            quote=quote_clean[:300],
            note=note,
            metadata={
                "start_char": start_char,
                "end_char": end_char,
            },
        )
    return ev_id

def add_claim(
    g: MemoryGraph,
    predicate: str,
    subject_id: str,
    *,
    object_id: Optional[str] = None,
    object_text: Optional[str] = None,
    evidence_id: str,
    confidence: float = 1.0,
    valid_from: Optional[str] = None,
) -> str:
    """
    Create a deterministic claim id. If same claim repeats, we just attach more evidence.
    """
    obj_part = object_id if object_id is not None else (object_text or "")
    cid = stable_id("claim", predicate, subject_id, obj_part)

    if cid not in g.claims:
        g.claims[cid] = Claim(
            claim_id=cid,
            predicate=predicate,  # type: ignore
            subject_id=subject_id,
            object_id=object_id,
            object_text=object_text,
            confidence=confidence,
            status="active",
            valid_from=valid_from,
            evidence_ids=[evidence_id],
            metadata={},
        )
    else:
        if evidence_id not in g.claims[cid].evidence_ids:
            g.claims[cid].evidence_ids.append(evidence_id)

    return cid


def extract_from_artifact_text(text: str) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
    """
    Returns:
    - issue_refs: list of issue numbers found as "#123"
    - user_mentions: list of usernames found as "@name"
    - patterns: list of (kind, issue_num) for special relations
    """
    issue_refs = [m.group(1) for m in RE_ISSUE_REF.finditer(text or "")]
    user_mentions = [m.group(1) for m in RE_USER_MENTION.finditer(text or "")]

    patterns = []
    t = (text or "").lower()

    # very simple heuristics for relationships
    if "blocked by" in t or "depends on" in t:
        for num in issue_refs:
            patterns.append(("blocked_by", num))

    if "duplicate of" in t:
        for num in issue_refs:
            patterns.append(("duplicate_of", num))

    if "assigning to" in t or "assigned to" in t or "will implement" in t or "i can take" in t:
        # ownership is inferred from @mentions
        for u in user_mentions:
            patterns.append(("mentions_owner", u))

    return issue_refs, user_mentions, patterns


def run_rule_extraction(g: MemoryGraph) -> MemoryGraph:
    """
    Reads g.artifacts and produces entities/claims/evidence.
    """
    # Create a repo entity once (from any artifact metadata)
    repo_owner = None
    repo_name = None
    for a in g.artifacts.values():
        repo_owner = a.metadata.get("repo_owner")
        repo_name = a.metadata.get("repo_name")
        if repo_owner and repo_name:
            break

    if repo_owner and repo_name:
        repo_eid = ensure_entity(g, "repo", f"{repo_owner}/{repo_name}", extra_key=f"{repo_owner}/{repo_name}")
    else:
        repo_eid = ensure_entity(g, "repo", "unknown/unknown", extra_key="unknown/unknown")

    for artifact_id, a in g.artifacts.items():
        kind = a.metadata.get("kind")

        # If this artifact belongs to an issue, ensure an issue entity exists.
        issue_num = a.metadata.get("issue_number")
        issue_eid = None
        if issue_num is not None:
            issue_eid = ensure_entity(g, "issue", f"#{issue_num}", extra_key=str(issue_num))

            # claim: repo has issue (as "mentions" edge, for connectivity)
            ev_repo = add_evidence(g, artifact_id, a.text[:200], note="issue belongs to repo")
            add_claim(g, "mentions", repo_eid, object_id=issue_eid, evidence_id=ev_repo, confidence=1.0)

        # person entity for author
        if a.author:
            ensure_entity(g, "person", a.author, extra_key=a.author)

        # issue metadata claims: labels and state only from issue artifact
        if kind == "issue" and issue_eid is not None:
            state = a.metadata.get("state")
            if state:
                ev_state = add_evidence(g, artifact_id, f"state: {state}", note="issue state from metadata")
                add_claim(g, "is_state", issue_eid, object_text=str(state), evidence_id=ev_state, confidence=1.0)

            for lab in a.metadata.get("labels", []) or []:
                label_eid = ensure_entity(g, "label", lab, extra_key=lab)
                ev_lab = add_evidence(g, artifact_id, f"label: {lab}", note="issue label from metadata")
                add_claim(g, "has_label", issue_eid, object_id=label_eid, evidence_id=ev_lab, confidence=1.0)

        # text-based extraction from issue bodies + comments
        if issue_eid is not None:
            _, _, patterns = extract_from_artifact_text(a.text)

            for kind2, val in patterns:
                if kind2 in ("blocked_by", "duplicate_of") and val.isdigit():
                    other_issue = ensure_entity(g, "issue", f"#{val}", extra_key=str(val))
                    ev = add_evidence(g, artifact_id, a.text[:250], note=f"detected relation: {kind2} #{val}")
                    add_claim(g, kind2, issue_eid, object_id=other_issue, evidence_id=ev, confidence=0.8, valid_from=a.created_at)

                if kind2 == "mentions_owner":
                    person = ensure_entity(g, "person", val, extra_key=val)
                    ev = add_evidence(g, artifact_id, a.text[:250], note=f"detected owner mention: @{val}")
                    add_claim(g, "mentions_owner", issue_eid, object_id=person, evidence_id=ev, confidence=0.75, valid_from=a.created_at)

    return g