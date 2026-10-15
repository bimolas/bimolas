#!/usr/bin/env python3
"""One-time local Spotify OAuth helper; it prints a refresh token only to the local terminal."""
from __future__ import annotations
import base64, json, os, secrets, threading, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

REDIRECT_URI = "http://127.0.0.1:8765/callback"

def main() -> int:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your local shell first.")
        return 2
    state, result = secrets.token_urlsafe(24), {}
    params = {"client_id":client_id,"response_type":"code","redirect_uri":REDIRECT_URI,"scope":"user-read-currently-playing","state":state}
    authorize_url = "https://accounts.spotify.com/authorize?" + urlencode(params)

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return
        def do_GET(self) -> None:
            parsed, query = urlparse(self.path), parse_qs(urlparse(self.path).query)
            returned_state = (query.get("state") or [""])[0]
            if parsed.path != "/callback" or returned_state != state:
                result["error"] = "state mismatch or wrong callback"
                self.send_response(400); self.end_headers()
                self.wfile.write(b"Spotify authorization state mismatch. You can close this tab.")
                return
            error, code = (query.get("error") or [""])[0], (query.get("code") or [""])[0]
            if error:
                result["error"] = error
            elif code:
                result["code"] = code
            else:
                result["error"] = "authorization code missing"
            good = bool(code and not error)
            self.send_response(200 if good else 400)
            self.send_header("Content-Type","text/html; charset=utf-8"); self.end_headers()
            message = "Spotify authorization received. Return to your terminal." if good else "Spotify authorization was not completed."
            self.wfile.write(f"<html><body style='font:16px sans-serif;background:#101820;color:#e6edf3;padding:3rem'><h2>{message}</h2><p>You can close this tab.</p></body></html>".encode())

    server = HTTPServer(("127.0.0.1",8765), CallbackHandler)
    server.timeout = 180
    print("Opening Spotify approval in your browser.")
    print("Waiting for approval at", REDIRECT_URI)
    threading.Thread(target=lambda: webbrowser.open(authorize_url),daemon=True).start()
    try:
        while not result:
            server.handle_request()
    finally:
        server.server_close()
    if result.get("error"):
        print("Spotify authorization failed:",result["error"])
        return 1
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = Request("https://accounts.spotify.com/api/token",
        data=urlencode({"grant_type":"authorization_code","code":result["code"],"redirect_uri":REDIRECT_URI}).encode(),
        headers={"Authorization":f"Basic {basic}","Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urlopen(req,timeout=20) as response:
            token_data = json.load(response)
    except (HTTPError,URLError,TimeoutError) as exc:
        print("Token exchange failed:",type(exc).__name__,str(exc))
        return 1
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print("Spotify did not return a refresh token. Check the app settings and try again.")
        return 1
    print("\nCopy this refresh token directly into GitHub Actions secret SPOTIFY_REFRESH_TOKEN:")
    print(refresh_token)
    print("\nDo not commit it or paste it into chat. Treat it like a password.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
