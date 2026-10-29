"""Cache of your playlists and liked songs, so the menu opens instantly.

The menu shows what is cached and refreshes it in the background for next time.
"""

import json
import subprocess
import time
from pathlib import Path

import spotify

CACHE_DIR = Path.home() / ".cache" / "spotify-menu"
SCRIPT = Path(__file__).resolve().parent / "spotify-menu"
REFRESH_AFTER_SECONDS = 60


def load(name):
    try:
        return json.loads((CACHE_DIR / f"{name}.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save(name, data):
    # write then rename, so a menu reading at the same time never sees half a file
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_DIR / f".{name}.json.tmp"
    temporary.write_text(json.dumps(data))
    temporary.replace(CACHE_DIR / f"{name}.json")


def cached(name, fetch):
    data = load(name)
    if data is None:
        data = fetch()
        save(name, data)
    return data


def playlists():
    return cached("playlists", spotify.my_playlists)


def liked_tracks():
    return cached("liked", spotify.liked_tracks)


def user_id():
    return cached("user_id", lambda: spotify.api("GET", "/me")["id"])


def liked_songs_uri():
    return f"spotify:user:{user_id()}:collection"


def playlist_tracks(playlist):
    # a playlist's snapshot id changes whenever it is edited, so it makes a safe cache key
    fetch = lambda: spotify.playlist_tracks(playlist["id"])
    if not playlist.get("snapshot_id"):
        return fetch()
    return cached(f"playlist-{playlist['id']}-{playlist['snapshot_id']}", fetch)


def refresh():
    save("playlists", spotify.my_playlists())
    save("liked", spotify.liked_tracks())


def refresh_in_background(force=False):
    """Start `spotify-menu refresh` detached, unless the cache was refreshed just now."""
    playlists_file = CACHE_DIR / "playlists.json"
    if not force and playlists_file.exists() and time.time() - playlists_file.stat().st_mtime < REFRESH_AFTER_SECONDS:
        return
    subprocess.Popen([str(SCRIPT), "refresh"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
