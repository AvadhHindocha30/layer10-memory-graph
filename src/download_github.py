from __future__ import annotations

import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, List
import re


def gh_get(url: str, token: str | None) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def build_corpus(owner: str, repo: str, issue_numbers: List[int], token: str | None) -> Dict[str, Any]:
    items = []

    for num in issue_numbers:
        issue = gh_get(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}", token)

        # skip PRs (GitHub returns PRs in issues endpoint too)
        if "pull_request" in issue:
            continue

        comments = []
        if issue.get("comments", 0) > 0 and issue.get("comments_url"):
            raw_comments = gh_get(issue["comments_url"], token)
            for c in raw_comments:
                comments.append({
                    "comment_id": str(c.get("id")),
                    "created_at": c.get("created_at"),
                    "author": (c.get("user") or {}).get("login"),
                    "text": c.get("body") or "",
                })

        items.append({
            "type": "issue",
            "number": issue.get("number"),
            "title": issue.get("title") or "",
            "state": issue.get("state") or "",
            "labels": [lab.get("name") for lab in (issue.get("labels") or []) if isinstance(lab, dict)],
            "url": issue.get("html_url"),
            "created_at": issue.get("created_at"),
            "author": (issue.get("user") or {}).get("login"),
            "body": issue.get("body") or "",
            "comments": comments,
        })

        time.sleep(0.3)  # be polite

    return {
        "source": "github",
        "repo": {"owner": owner, "name": repo},
        "items": items,
    }


def list_issues(owner: str, repo: str, token: str | None, limit: int) -> list[int]:
    """
    Returns up to `limit` issue numbers (skips PRs).
    Uses GitHub REST issues listing endpoint with pagination.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    out: list[int] = []
    page = 1
    per_page = 100

    while len(out) < limit:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page={per_page}&page={page}"
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        items = r.json()
        if not items:
            break

        for it in items:
            if "pull_request" in it:
                continue
            num = it.get("number")
            if isinstance(num, int):
                out.append(num)
            if len(out) >= limit:
                break

        page += 1

    return out

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--issues", nargs="*", type=int, default=None, help="Issue numbers e.g. 1 2 3")
    p.add_argument("--limit", type=int, default=0, help="If >0, auto-download first N issues (skips PRs).")
    p.add_argument("--out", default="data/raw/github_corpus.json")
    p.add_argument("--token", default=None, help="Optional GitHub token (recommended to avoid rate limits)")
    args = p.parse_args()

    issue_numbers = args.issues or []
    if args.limit and args.limit > 0:
        issue_numbers = list_issues(args.owner, args.repo, args.token, args.limit)

    if not issue_numbers:
        raise SystemExit("Provide --issues ... OR --limit N")

    corpus = build_corpus(args.owner, args.repo, issue_numbers, args.token)
    Path(args.out).write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Wrote {args.out} with {len(corpus['items'])} issues")


if __name__ == "__main__":
    main()