from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from src.schema import MemoryGraph, Artifact, stable_id

# reuse the existing helper functions for entities/claims/evidence
from src.extract_rules import ensure_entity, add_evidence, add_claim


def load_demo(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ingest_demo_corpus(raw_path: str) -> MemoryGraph:
    data = load_demo(raw_path)

    source = data.get("source", "demo")
    repo = data.get("repo", {})
    owner = repo.get("owner", "unknown")
    name = repo.get("name", "unknown")

    g = MemoryGraph()

    # Create repo entity once (helps navigation)
    repo_key = f"{owner}/{name}"
    repo_id = ensure_entity(g, "repo", repo_key, extra_key=repo_key)

    for item in data.get("items", []):
        if item.get("type") != "issue":
            continue

        issue_num = str(item.get("number"))
        issue_url = item.get("url")
        issue_author = item.get("author")
        issue_created = item.get("created_at")
        issue_text = (item.get("title", "") + "\n\n" + item.get("body", "")).strip()

        issue_artifact_id = stable_id("artifact", source, owner, name, "issue", issue_num)

        # store issue artifact
        g.artifacts[issue_artifact_id] = Artifact(
            artifact_id=issue_artifact_id,
            source=source,
            url=issue_url,
            created_at=issue_created,
            author=issue_author,
            text=issue_text,
            metadata={
                "repo_owner": owner,
                "repo_name": name,
                "kind": "issue",
                "issue_number": int(issue_num),
                "state": item.get("state"),
                "labels": item.get("labels", []),
            },
        )

        # create issue entity
        issue_id = ensure_entity(g, "issue", f"#{issue_num}", extra_key=issue_num)

        # link repo -> issue (grounded using the issue artifact text)
        ev_repo = add_evidence(
            g,
            issue_artifact_id,
            (issue_text[:200] or f"issue #{issue_num}"),
            note="repo mentions issue",
        )
        add_claim(g, "mentions", repo_id, object_id=issue_id, evidence_id=ev_repo, confidence=1.0)

        # link issue -> author (so person nodes have edges)
        if issue_author:
            person_id = ensure_entity(g, "person", issue_author, extra_key=issue_author)
            ev_auth = add_evidence(
                g,
                issue_artifact_id,
                f"author: {issue_author}",
                note="derived from issue metadata",
            )
            add_claim(
                g,
                "authored_issue",
                issue_id,
                object_id=person_id,
                evidence_id=ev_auth,
                confidence=1.0,
                valid_from=issue_created,
            )

        # store comment artifacts + link issue -> commenter
        for c in item.get("comments", []):
            comment_id = str(c.get("comment_id"))
            c_created = c.get("created_at")
            c_author = c.get("author")
            c_text = (c.get("text") or "").strip()

            c_artifact_id = stable_id("artifact", source, owner, name, "comment", issue_num, comment_id)

            g.artifacts[c_artifact_id] = Artifact(
                artifact_id=c_artifact_id,
                source=source,
                url=issue_url,
                created_at=c_created,
                author=c_author,
                text=c_text,
                metadata={
                    "repo_owner": owner,
                    "repo_name": name,
                    "kind": "comment",
                    "issue_number": int(issue_num),
                    "comment_id": comment_id,
                },
            )

            if c_author:
                person_id = ensure_entity(g, "person", c_author, extra_key=c_author)
                ev_com = add_evidence(
                    g,
                    c_artifact_id,
                    f"commenter: {c_author}",
                    note="derived from comment metadata",
                )
                add_claim(
                    g,
                    "commented_on",
                    issue_id,
                    object_id=person_id,
                    evidence_id=ev_com,
                    confidence=1.0,
                    valid_from=c_created,
                )

    return g


def main():
    g = ingest_demo_corpus("data/raw/demo_corpus.json")
    print(f"Artifacts ingested: {len(g.artifacts)}")
    print(f"Entities: {len(g.entities)}  Claims: {len(g.claims)}  Evidences: {len(g.evidences)}")
    for i, k in enumerate(list(g.artifacts.keys())[:3]):
        a = g.artifacts[k]
        print(f"- {i+1}. {a.artifact_id} ({a.metadata.get('kind')}) author={a.author}")


if __name__ == "__main__":
    main()