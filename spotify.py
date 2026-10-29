"""Small Spotify Web API client for browsing your library and searching."""

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from auth import access_token

API_URL = "https://api.spotify.com/v1"
LIKED_SONGS_LIMIT = 500
SEARCH_TRACKS = 30


class SpotifyError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def api(method, path, params=None, body=None):
    url = API_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {access_token()}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content = response.read()
            is_json = "json" in (response.headers.get("Content-Type") or "")
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = error.reason
        raise SpotifyError(f"Spotify API error {error.code}: {message}", error.code) from None
    # player commands answer with a plain text snapshot id, which we don't need
    return json.loads(content) if content and is_json else None


def paginate(path, params=None, limit=None):
    """Yield items from a paged endpoint, following the next links."""
    page = api("GET", path, {"limit": 50, **(params or {})})
    count = 0
    while page:
        for item in page["items"]:
            yield item
            count += 1
            if limit and count >= limit:
                return
        next_url = page.get("next")
        page = api("GET", next_url.removeprefix(API_URL)) if next_url else None


# library

def my_playlists():
    return [playlist for playlist in paginate("/me/playlists") if playlist]


def liked_tracks():
    return [entry["track"] for entry in paginate("/me/tracks", limit=LIKED_SONGS_LIMIT)]


def playlist_tracks(playlist_id):
    """Tracks of a playlist, or None when Spotify won't list them (not ours)."""
    try:
        entries = list(paginate(f"/playlists/{playlist_id}/items"))
    except SpotifyError as error:
        if error.status in (403, 404):
            return None
        raise
    tracks = (entry.get("item") or entry.get("track") for entry in entries)
    return [track for track in tracks if track and track.get("type") == "track"]


def is_liked(uri):
    return api("GET", "/me/library/contains", {"uris": uri})[0]


def set_liked(uri, liked):
    # the older /me/tracks endpoints answer 403 for new apps, /me/library takes any uri
    api("PUT" if liked else "DELETE", "/me/library", {"uris": uri})


def add_to_playlist(playlist_id, uri):
    api("POST", f"/playlists/{playlist_id}/items", body={"uris": [uri]})


def album_tracks(album_id):
    return list(paginate(f"/albums/{album_id}/tracks"))


def search(query):
    """Up to 30 tracks and 10 artists, albums and playlists matching the query."""
    def search_page(kinds, offset):
        return api("GET", "/search", {"q": query, "type": kinds, "limit": 10, "offset": offset})

    # Spotify caps a search at 10 results, so fetch more track pages side by side
    with ThreadPoolExecutor() as pool:
        first_page = pool.submit(search_page, "track,album,artist,playlist", 0)
        track_pages = [pool.submit(search_page, "track", offset)
                       for offset in range(10, SEARCH_TRACKS, 10)]
        results = first_page.result()
        for page in track_pages:
            results["tracks"]["items"] += page.result()["tracks"]["items"]

    return {kind: [item for item in found["items"] if item]
            for kind, found in results.items()}

