# Connect the live Spotify panel

The profile can show the currently playing Spotify track and a personal playlist link. The workflow reads the current track and updates the README; it does not play audio.

## 1. Create a Spotify app

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app.
2. Add this exact Redirect URI to the app settings:

   `http://127.0.0.1:8765/callback`

3. Copy the Client ID and Client Secret. Keep the secret local; do not put credentials in source code.

## 2. Generate your refresh token locally

Use Python 3.10+ from the repository root. Set the credentials in your local shell, then run the helper:

Linux / macOS:

```bash
export SPOTIFY_CLIENT_ID="your-client-id"
export SPOTIFY_CLIENT_SECRET="your-client-secret"
python scripts/spotify_auth.py
```

PowerShell:

```powershell
$env:SPOTIFY_CLIENT_ID = "your-client-id"
$env:SPOTIFY_CLIENT_SECRET = "your-client-secret"
python scripts/spotify_auth.py
```

A browser opens for approval. The helper prints a refresh token after approval. Copy it directly to GitHub; do not commit the token or paste it into chat.

## 3. Add GitHub Actions secrets

In `bimolas/bimolas`, open **Settings → Secrets and variables → Actions → New repository secret** and add:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`

Then open **Settings → Secrets and variables → Actions → Variables** and create:

- `SPOTIFY_PLAYLIST_URL` — your public Spotify playlist URL, such as `https://open.spotify.com/playlist/...`

## 4. Start the workflow

Open the repository's **Actions** tab, choose **Refresh Spotify now-playing panel**, and select **Run workflow**. The panel refreshes on a schedule once the secrets exist; scheduled jobs can run later than the exact cron minute.

The app must have the `user-read-currently-playing` scope. If access is revoked or the refresh token expires, run the local helper again and replace `SPOTIFY_REFRESH_TOKEN`.

## Privacy

The public README shows only the track and artist currently playing, plus the playlist link you configure. Never commit Client Secrets or refresh tokens.