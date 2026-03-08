from __future__ import annotations

from typing import Dict, List, Tuple
from datetime import datetime

from src.schema import MemoryGraph


def _ts(s: str | None) -> Tuple[int, str]:
    """
    Convert ISO time to sortable key. If missing, treat as very old.
    """
    if not s:
        return (0, "")
    try:
        # Works for "...Z" timestamps too
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (int(dt.timestamp()), s)
    except Exception:
        return (0, s)


def supersede_by_latest(g: MemoryGraph, predicate: str) -> None:
    """
    For a given predicate, if multiple claims exist per subject,
    mark all but the latest as superseded.
    """
    by_subject: Dict[str, List[str]] = {}
    for cid, c in g.claims.items():
        if c.predicate != predicate:
            continue
        by_subject.setdefault(c.subject_id, []).append(cid)

    for subj, cids in by_subject.items():
        if len(cids) <= 1:
            continue

        # choose latest using claim.valid_from (fallback: any evidence artifact time)
        scored = []
        for cid in cids:
            c = g.claims[cid]
            best_time = c.valid_from

            # fallback: look at evidence artifact timestamps
            if not best_time and c.evidence_ids:
                ev0 = g.evidences.get(c.evidence_ids[0])
                if ev0:
                    art = g.artifacts.get(ev0.artifact_id)
                    if art:
                        best_time = art.created_at

            scored.append(( _ts(best_time), cid ))

        scored.sort()  # oldest -> newest
        keep = scored[-1][1]

        for _, cid in scored[:-1]:
            g.claims[cid].status = "superseded"
            g.claims[cid].valid_to = g.claims[keep].valid_from


def run_dedup_and_versioning(g: MemoryGraph) -> MemoryGraph:
    """
    Minimal dedup/versioning pass.
    - keep latest is_state per issue
    - keep latest mentions_owner per issue
    """
    supersede_by_latest(g, "is_state")
    supersede_by_latest(g, "mentions_owner")
    return g