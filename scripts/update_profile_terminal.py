#!/usr/bin/env python3
"""Refresh the custom terminal card with public GitHub profile data."""
from __future__ import annotations
import json, os, sys
from io import BytesIO
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape
from PIL import Image, ImageOps

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


ASCII_RAMP = " .,:;irsXA253hMHGS#9B&@"

def render_ascii_portrait(avatar_url: str) -> str:
    """Convert the public GitHub avatar to coloured ASCII embedded inside the SVG."""
    if not avatar_url:
        return '<text x="12" y="140" fill="#91d7b1" font-size="10">profile avatar unavailable</text>'
    try:
        request = Request(avatar_url, headers={"User-Agent": "bimolas-profile-terminal"})
        with urlopen(request, timeout=20) as response:
            image_bytes = response.read()
        with Image.open(BytesIO(image_bytes)) as image:
            resized = ImageOps.fit(image.convert("RGB"), (48, 30), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        lines: list[str] = []
        for y in range(resized.height):
            cells: list[tuple[str, str]] = []
            for x in range(resized.width):
                red, green, blue = resized.getpixel((x, y))
                luminance = (299 * red + 587 * green + 114 * blue) // 1000
                index = min(len(ASCII_RAMP) - 1, round(luminance * (len(ASCII_RAMP) - 1) / 255))
                character = ASCII_RAMP[index]
                adjusted = tuple(min(255, int(channel * 0.78 + 46)) for channel in (red, green, blue))
                colour = "#" + "".join(f"{channel:02x}" for channel in adjusted)
                cells.append((character, colour))
            runs: list[str] = []
            current_colour, current_text = "", ""
            for character, colour in cells:
                if colour != current_colour and current_text:
                    runs.append(f'<tspan fill="{current_colour}">{escape(current_text)}</tspan>')
                    current_text = ""
                current_colour = colour
                current_text += character
            if current_text:
                runs.append(f'<tspan fill="{current_colour}">{escape(current_text)}</tspan>')
            baseline = 24 + y * 8.2
            lines.append(
                f'<text x="6" y="{baseline:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
                f'font-size="8.5" font-weight="700" letter-spacing="-.25" xml:space="preserve">{"".join(runs)}</text>'
            )
        return "\n".join(lines)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Avatar-to-ASCII rendering failed ({type(exc).__name__}); using fallback portrait.", file=sys.stderr)
        return '<text x="12" y="140" fill="#91d7b1" font-size="10">avatar render unavailable</text>'

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
        "ASCII_PORTRAIT": render_ascii_portrait(str(profile.get("avatar_url") or "")),
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
