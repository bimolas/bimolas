#!/usr/bin/env python3
"""Refresh the public Spotify card and its linked README text without exposing secrets."""
from __future__ import annotations
import base64, html, os, re, sys, json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
SVG_PATH = ROOT / "assets" / "spotify-now-playing.svg"
START_MARKER = "<!-- SPOTIFY-NOW-PLAYING:START -->"
END_MARKER = "<!-- SPOTIFY-NOW-PLAYING:END -->"

def esc(value: str) -> str:
    return html.escape(value, quote=True)

def shorten(value: str, limit: int = 49) -> str:
    clean = " ".join((value or "").split())
    return clean if len(clean) <= limit else clean[:limit - 1].rstrip() + "…"

def render_panel(state: str, title: str = "", artist: str = "", playlist_linked: bool = False) -> str:
    if state == "playing":
        eyebrow, headline, subline, note, accent, status = "NOW PLAYING / SPOTIFY", shorten(title), shorten(artist, 64), "LIVE STATUS · REFRESHED BY GITHUB ACTIONS", "#1ed760", "PLAYING"
    elif state == "idle":
        eyebrow, headline, subline, note, accent, status = "SPOTIFY / IDLE", "Nothing playing right now", "Start playback and the track will appear here.", "WAITING FOR THE NEXT TRACK", "#8b949e", "IDLE"
    elif state == "error":
        eyebrow, headline, subline, note, accent, status = "SPOTIFY / RECONNECT", "Spotify needs re-authorization", "Check the Actions run; the saved token may need replacing.", "AUTHORIZATION REQUIRED", "#e3b341", "RECONNECT"
    else:
        eyebrow, headline, subline, note, accent, status = "SPOTIFY / SETUP", "Your soundtrack, live", "Connect Spotify once to show the track playing on your account.", "WAITING FOR SPOTIFY CREDENTIALS", "#1ed760", "NOT LINKED"
    bars = []
    heights = [12, 21, 15, 29, 17, 25, 11, 22, 15, 27, 13, 20, 10]
    for i, height in enumerate(heights):
        x, delay = 1050 + i * 8, (i * 0.09) % 1.1
        bars.append(f'<rect x="{x}" y="{83-height}" width="4" height="{height}" rx="2" fill="{accent}" style="transform-origin:bottom;animation:eq 1.05s ease-in-out {delay:.2f}s infinite alternate"/>')
    playlist_label = "PLAYLIST LINKED" if playlist_linked else "ADD PLAYLIST URL"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="170" viewBox="0 0 1200 170" role="img" aria-labelledby="title desc">
  <title id="title">Spotify listening status: {esc(status)}</title>
  <desc id="desc">A custom Spotify-inspired dark panel showing current track status. This visual does not play audio.</desc>
  <defs><linearGradient id="panel" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111a20"/><stop offset="1" stop-color="#0a0f14"/></linearGradient>
  <style>text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}.muted{{fill:#8b9aa7}}.white{{fill:#e6edf3}}.small{{font-size:10px;letter-spacing:1.2px}}@keyframes eq{{from{{transform:scaleY(.32);opacity:.55}}to{{transform:scaleY(1);opacity:1}}}}</style></defs>
  <rect width="1200" height="170" rx="15" fill="url(#panel)" stroke="#2b3c3e"/><rect x="1" y="1" width="1198" height="168" rx="14" fill="none" stroke="#1ed760" stroke-opacity=".12"/>
  <circle cx="68" cy="85" r="31" fill="#1ed760"/><path d="M48 75Q68 68 88 78M51 85Q68 80 85 88M55 95Q68 91 81 98" fill="none" stroke="#07110a" stroke-width="4.5" stroke-linecap="round"/>
  <text x="122" y="39" class="small" fill="{accent}">{esc(eyebrow)}</text><text x="122" y="72" class="white" font-size="23" font-weight="700">{esc(headline)}</text><text x="122" y="98" class="muted" font-size="14">{esc(subline)}</text>
  <line x1="122" y1="118" x2="940" y2="118" stroke="#273740"/><text x="122" y="140" class="muted small">{esc(note)}</text><text x="940" y="140" text-anchor="end" fill="#93a4ad" class="small">{esc(playlist_label)}</text>
  <g>{"".join(bars)}</g><circle cx="1137" cy="36" r="4" fill="{accent}"><animate attributeName="opacity" values=".35;1;.35" dur="2s" repeatCount="indefinite"/></circle><text x="1150" y="40" text-anchor="end" fill="{accent}" class="small">{esc(status)}</text>
</svg>'''

def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = Request("https://accounts.spotify.com/api/token", data=urlencode({"grant_type":"refresh_token","refresh_token":refresh_token}).encode(),
                  headers={"Authorization":f"Basic {basic}","Content-Type":"application/x-www-form-urlencoded"}, method="POST")
    with urlopen(req, timeout=20) as response:
        data = json.load(response)
    token = data.get("access_token")
    if not token:
        raise ValueError("Spotify did not return an access token.")
    return token

def current_track(access_token: str) -> dict | None:
    req = Request("https://api.spotify.com/v1/me/player/currently-playing",
                  headers={"Authorization":f"Bearer {access_token}","Accept":"application/json"})
    try:
        with urlopen(req, timeout=20) as response:
            if response.status == 204:
                return None
            payload = json.load(response)
            if not payload or not payload.get("is_playing") or not payload.get("item"):
                return None
            return payload
    except HTTPError as exc:
        if exc.code == 204:
            return None
        raise

def update_readme(replacement: str) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    start, end = text.find(START_MARKER), text.find(END_MARKER)
    if start < 0 or end < start:
        raise ValueError("Spotify markers were not found in README.md.")
    content_start = start + len(START_MARKER)
    README_PATH.write_text(text[:content_start] + "\n    " + replacement + "\n    " + text[end:], encoding="utf-8")

def markdown_escape(value: str) -> str:
    escaped = re.sub(r"([\\*_{}\[\]()<>#+\-.!|])", r"\\\1", value)
    return escaped.replace(chr(96), "\\" + chr(96))

def main() -> int:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip()
    playlist_url = os.environ.get("SPOTIFY_PLAYLIST_URL", "").strip()
    state, title, artist = "setup", "", ""
    if not (client_id and client_secret and refresh_token):
        markdown = "Spotify is not connected yet. Add the Spotify Actions secrets described in [the setup guide](SPOTIFY_SETUP.md) to enable live status."
    else:
        try:
            payload = current_track(refresh_access_token(client_id, client_secret, refresh_token))
            if payload:
                item = payload["item"]
                title = str(item.get("name") or "Unknown track")
                artist_list = item.get("artists") or []
                artist = ", ".join(str(a.get("name") or "") for a in artist_list if a.get("name")) or "Unknown artist"
                link = str((item.get("external_urls") or {}).get("spotify") or "https://open.spotify.com/")
                state = "playing"
                markdown = f"🎧 **Now playing:** [{markdown_escape(title)} — {markdown_escape(artist)}]({link})"
            else:
                state = "idle"
                markdown = "🎧 Nothing is playing right now. This panel will update when Spotify playback is active."
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            print(f"Spotify refresh failed ({type(exc).__name__}). Check app credentials and token.", file=sys.stderr)
            state = "error"
            markdown = "Spotify could not return the current track. Check the latest workflow run; the saved token may need re-authorization."
    if playlist_url:
        if playlist_url.startswith("https://open.spotify.com/"):
            markdown += f" · [Open playlist ↗]({playlist_url})"
        else:
            print("SPOTIFY_PLAYLIST_URL is not a Spotify HTTPS link; ignoring it.", file=sys.stderr)
    SVG_PATH.write_text(render_panel(state, title, artist, bool(playlist_url)), encoding="utf-8")
    update_readme(markdown)
    print(f"Rendered Spotify panel state: {state}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
