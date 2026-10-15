#!/usr/bin/env python3
"""Refresh the custom terminal card with public GitHub profile data."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
USERNAME = os.environ.get("GITHUB_USERNAME", "bimolas")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def request_json(url: str, payload: dict | None = None) -> dict | list:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "bimolas-profile-terminal"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
        return json.load(response)

def get_owned_repositories() -> list[dict]:
    results: list[dict] = []
    for page in range(1, 11):
        batch = request_json(f"https://api.github.com/users/{USERNAME}/repos?type=owner&sort=updated&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("GitHub returned an unexpected repositories response.")
        results.extend(batch)
        if len(batch) < 100:
            break
    return results

def get_commit_contributions_last_year() -> str:
    if not TOKEN:
        return "—"
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=365)).isoformat(timespec="seconds").replace("+00:00", "Z")
    end = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    query = """
    query ($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) { totalCommitContributions }
      }
    }
    """
    try:
        result = request_json("https://api.github.com/graphql", {"query": query, "variables": {"login": USERNAME, "from": start, "to": end}})
        if not isinstance(result, dict) or result.get("errors"):
            return "—"
        value = ((result.get("data") or {}).get("user") or {}).get("contributionsCollection", {}).get("totalCommitContributions")
        return f"{int(value):,}" if value is not None else "—"
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError):
        return "—"

def main() -> int:
    try:
        profile = request_json(f"https://api.github.com/users/{USERNAME}")
        repos = get_owned_repositories()
    except (HTTPError, URLError, TimeoutError, ValueError, TypeError) as exc:
        print(f"Could not refresh GitHub profile data: {exc}", file=sys.stderr)
        return 1
    original_repos = [repo for repo in repos if not repo.get("fork", False)]
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in original_repos)
    language_counts = Counter(repo.get("language") for repo in original_repos if repo.get("language"))
    languages = " · ".join(name for name, _ in language_counts.most_common(3)) or "—"
    now = datetime.now(timezone.utc)
    values = {
        "PUBLIC_REPOS": f"{int(profile.get('public_repos', len(repos))):,}",
        "REPO_STARS": f"{stars:,}",
        "COMMITS_YEAR": escape(get_commit_contributions_last_year()),
        "FOLLOWERS": f"{int(profile.get('followers') or 0):,}",
        "LANGUAGES": escape(languages),
        "SYNC_TIME": escape("synced " + now.strftime("%Y-%m-%d UTC")),
    }
    source = ROOT / "assets" / "terminal-card.template.svg"
    destination = ROOT / "assets" / "terminal-card.svg"
    rendered = source.read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    destination.write_text(rendered, encoding="utf-8")
    print("Updated the terminal card with public GitHub data.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
