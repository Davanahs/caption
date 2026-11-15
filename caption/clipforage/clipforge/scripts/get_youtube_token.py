"""
Interactive script to authorize YouTube account and retrieve long-lived YOUTUBE_REFRESH_TOKEN.
"""
import os
import re
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TOKEN_DIR = Path(__file__).resolve().parent.parent / "tokens"
TOKEN_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_FILE = TOKEN_DIR / "youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def load_env_credentials():
    client_id = None
    client_secret = None
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("YOUTUBE_CLIENT_ID="):
                    client_id = line.split("=", 1)[1].strip()
                elif line.startswith("YOUTUBE_CLIENT_SECRET="):
                    client_secret = line.split("=", 1)[1].strip()
    return client_id, client_secret

def update_env_refresh_token(refresh_token):
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "YOUTUBE_REFRESH_TOKEN=" in content:
        content = re.sub(
            r"^YOUTUBE_REFRESH_TOKEN=.*$",
            f"YOUTUBE_REFRESH_TOKEN={refresh_token}",
            content,
            flags=re.MULTILINE
        )
    else:
        content += f"\nYOUTUBE_REFRESH_TOKEN={refresh_token}\n"

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    print("=" * 60)
    print("  ClipForge — YouTube OAuth Authorization")
    print("=" * 60)

    client_id, client_secret = load_env_credentials()
    if not client_id or not client_secret:
        print("[ERROR] YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET not found in .env!")
        return

    print(f"\n[OK] Using Client ID: {client_id[:20]}...")
    print("[INFO] Starting local authorization listener on port 8080...")
    print("[INFO] A browser window will open shortly.")
    print("       👉 Log in with the Google Account that OWNS your YouTube channel.")
    print("       👉 Click 'Continue' / 'Allow' on the permission screen.\n")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    # Run local server on port 8080 (which is in Authorized redirect URIs)
    creds = flow.run_local_server(
        port=8080,
        prompt="consent",
        access_type="offline"
    )

    refresh_token = creds.refresh_token
    if not refresh_token:
        print("\n[WARNING] No refresh token returned. (If you previously authorized, Google may not re-send it unless access is revoked).")
    else:
        print("\n" + "=" * 60)
        print("  🎉 SUCCESS! YOUTUBE OAUTH CONNECTED")
        print("=" * 60)
        print(f"\nREFRESH TOKEN: {refresh_token}\n")

        # Save to .env
        update_env_refresh_token(refresh_token)
        print("[OK] Automatically updated YOUTUBE_REFRESH_TOKEN in .env")

        # Save token file
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"[OK] Saved token credentials to {TOKEN_FILE}")

if __name__ == "__main__":
    main()

