from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Literal
import hashlib
import json
import time


EntityType = Literal["repo", "issue", "person", "label", "unknown"]
Predicate = Literal[
    "has_label",
    "is_state",
    "mentions_owner",
    "blocked_by",
    "duplicate_of",
    "mentions",
]


def stable_id(prefix: str, *parts: str) -> str:
    """
    Deterministic ID helper (good for dedup + reproducible outputs).
    Same (prefix, parts...) => same id.
    """
    raw = "||".join([prefix, *[p.strip().lower() for p in parts if p is not None]])
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{h}"


@dataclass
class Artifact:
    """
    A raw source item: issue body, comment, email, message, etc.
    This is the "ground truth" we always cite back to.
    """
    artifact_id: str
    source: str                     # e.g., "github"
    url: Optional[str]
    created_at: Optional[str]
    author: Optional[str]
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """
    Evidence is a pointer to a specific snippet inside an Artifact.
    Claims MUST always have at least one Evidence.
    """
    evidence_id: str
    artifact_id: str
    quote: str                      # short snippet (grounding)
    note: Optional[str] = None      # optional explanation
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    """
    Entity: something we want to remember and connect claims around.
    """
    entity_id: str
    entity_type: EntityType
    name: str
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Claim:
    """
    Claim: a typed relationship/fact extracted from artifacts.
    Always backed by evidence_ids.
    """
    claim_id: str
    predicate: Predicate
    subject_id: str
    object_id: Optional[str] = None        # another entity (preferred when possible)
    object_text: Optional[str] = None      # fallback when no entity exists
    confidence: float = 1.0
    status: Literal["active", "superseded"] = "active"

    # Optional time semantics (for "old truth vs new truth")
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

    evidence_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryGraph:
    """
    The complete stored memory. This is what retrieval + viz consume.
    """
    entities: Dict[str, Entity] = field(default_factory=dict)
    claims: Dict[str, Claim] = field(default_factory=dict)
    evidences: Dict[str, Evidence] = field(default_factory=dict)
    artifacts: Dict[str, Artifact] = field(default_factory=dict)
    merge_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "claims": {k: asdict(v) for k, v in self.claims.items()},
            "evidences": {k: asdict(v) for k, v in self.evidences.items()},
            "artifacts": {k: asdict(v) for k, v in self.artifacts.items()},
            "merge_log": self.merge_log,
            "generated_at": int(time.time()),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "MemoryGraph":
        g = MemoryGraph()
        for k, v in d.get("entities", {}).items():
            g.entities[k] = Entity(**v)
        for k, v in d.get("claims", {}).items():
            g.claims[k] = Claim(**v)
        for k, v in d.get("evidences", {}).items():
            g.evidences[k] = Evidence(**v)
        for k, v in d.get("artifacts", {}).items():
            g.artifacts[k] = Artifact(**v)
        g.merge_log = d.get("merge_log", [])
        return g