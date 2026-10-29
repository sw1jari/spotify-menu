"""Spotify OAuth login (PKCE) and token storage."""

import base64
import fcntl
import hashlib
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "spotify-menu"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_FILE = CONFIG_DIR / "token.json"
LOCK_FILE = CONFIG_DIR / "token.lock"

REDIRECT_PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-library-modify",
])


class AuthError(Exception):
    pass


def is_logged_in():
    return TOKEN_FILE.exists()


def missing_scopes():
    """Scopes the saved login wasn't granted, e.g. ones added in a newer version."""
    try:
        granted = json.loads(TOKEN_FILE.read_text()).get("scope", "").split()
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [scope for scope in SCOPES.split() if scope not in granted]


def saved_client_id():
    try:
        return json.loads(CONFIG_FILE.read_text())["client_id"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def load_client_id():
    client_id = saved_client_id()
    if not client_id:
        raise AuthError(f"No client id in {CONFIG_FILE}, run spotify-menu to log in")
    return client_id


def save_client_id(client_id):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"client_id": client_id}, indent=2) + "\n")


def request_token(fields):
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        token = json.load(response)

    # refresh responses may omit the refresh token, so keep the old one
    if "refresh_token" not in token and TOKEN_FILE.exists():
        token["refresh_token"] = json.loads(TOKEN_FILE.read_text())["refresh_token"]
    token["expires_at"] = time.time() + token["expires_in"] - 60

    # write then rename, so a reader never sees half a token file
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary = TOKEN_FILE.with_suffix(".tmp")
    temporary.touch(mode=0o600)
    temporary.write_text(json.dumps(token))
    temporary.replace(TOKEN_FILE)
    return token


def wait_for_callback(expected_state):
    """Serve one request on the redirect URI and return the auth code."""
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = query.get("code", [None])[0]
            result["state"] = query.get("state", [None])[0]
            result["error"] = query.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"spotify-menu: you can close this tab now.")

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", REDIRECT_PORT), CallbackHandler) as server:
        server.timeout = 300
        server.handle_request()

    if result.get("error"):
        raise AuthError(f"Login refused: {result['error']}")
    if not result.get("code") or result.get("state") != expected_state:
        raise AuthError("Login failed, no valid code in the callback")
    return result["code"]


def login(client_id):
    save_client_id(client_id)

    # PKCE: the challenge is the sha256 of a random verifier we keep secret
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    })
    print(f"Opening the browser, or visit:\n{url}")
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    code = wait_for_callback(state)
    request_token({
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    })
    print(f"Logged in, token saved to {TOKEN_FILE}")


def access_token():
    """Return a valid access token, refreshing it when it has expired."""
    if not TOKEN_FILE.exists():
        raise AuthError("Not logged in, run spotify-menu to log in")

    # only one thread or process may refresh, since a refresh can invalidate the old refresh token
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        token = json.loads(TOKEN_FILE.read_text())
        if time.time() < token["expires_at"]:
            return token["access_token"]

        # a revoked refresh token can't be fixed by retrying, so start a fresh login next time
        try:
            token = request_token({
                "client_id": load_client_id(),
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            })
        except urllib.error.HTTPError as error:
            if error.code != 400:
                raise
            TOKEN_FILE.unlink()
            raise AuthError("Login expired, run spotify-menu again to log in") from None
        return token["access_token"]
