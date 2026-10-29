"""Live tests against your Spotify account. They start the hidden client and play briefly."""

import importlib.machinery
import importlib.util
import time
import unittest
from pathlib import Path
from unittest import mock

import auth
import cache
import player
import spotify

# the script has no .py extension, so load it by path
SCRIPT = Path(__file__).resolve().parent.parent / "spotify-menu"
loader = importlib.machinery.SourceFileLoader("spotify_menu", str(SCRIPT))
menu = importlib.util.module_from_spec(importlib.util.spec_from_loader("spotify_menu", loader))
loader.exec_module(menu)

QUERY = "you are not alone michael jackson"
TRACK_NAME = "You Are Not Alone"


def wait_until_playing(text):
    for _ in range(10):
        current = player.now_playing()
        if current and text in current:
            return current
        time.sleep(1)
    return player.now_playing()


@unittest.skipUnless(auth.is_logged_in(), "not logged in, run spotify-menu first")
class LiveTest(unittest.TestCase):
    def tearDown(self):
        if player.is_running():
            player.playerctl("pause")

    def test_search(self):
        results = spotify.search(QUERY)
        self.assertIn(TRACK_NAME, [track["name"] for track in results["tracks"]])

    def test_like_and_unlike(self):
        # flip a known track's like and put it back, so your library ends up unchanged
        uri = next(track["uri"] for track in spotify.search(QUERY)["tracks"]
                   if track["name"] == TRACK_NAME)
        was_liked = spotify.is_liked(uri)
        try:
            spotify.set_liked(uri, not was_liked)
            self.assertEqual(spotify.is_liked(uri), not was_liked)
        finally:
            spotify.set_liked(uri, was_liked)
        self.assertEqual(spotify.is_liked(uri), was_liked)

    def test_add_to_playlist(self):
        # use a throwaway playlist, so none of your own playlists change
        uri = spotify.search(QUERY)["tracks"][0]["uri"]
        playlist = spotify.api("POST", "/me/playlists",
                               body={"name": "spotify-menu test", "public": False})
        try:
            spotify.add_to_playlist(playlist["id"], uri)
            self.assertEqual([track["uri"] for track in spotify.playlist_tracks(playlist["id"])], [uri])
        finally:
            spotify.api("DELETE", f"/playlists/{playlist['id']}/followers")

    def test_library(self):
        playlists = spotify.my_playlists()
        self.assertTrue(all("uri" in playlist for playlist in playlists))
        self.assertTrue(all("uri" in track for track in spotify.liked_tracks()))

        # tracks can only be listed for playlists you own
        my_id = spotify.api("GET", "/me")["id"]
        own = [playlist for playlist in playlists if playlist["owner"]["id"] == my_id]
        if own:
            self.assertIsInstance(spotify.playlist_tracks(own[0]["id"]), list)

    def test_search_menu_starts_client_and_plays(self):
        # start from nothing running, the menu has to bring up the hidden client itself
        player.quit()
        time.sleep(2)

        # stand in for dmenu: type the query, then pick the first track in the results
        def fake_dmenu(labels, prompt):
            if prompt == "search:":
                return QUERY
            return next(label for label in labels if label.startswith("♪"))

        with mock.patch.object(menu, "dmenu", fake_dmenu):
            self.assertTrue(menu.search_menu())
        self.assertIn(TRACK_NAME, wait_until_playing(TRACK_NAME) or "")
        self.assertEqual(player.playerctl("status"), "Playing")

    def test_typing_in_main_menu_searches(self):
        # type a query straight into the main menu, then pick the first result
        def fake_dmenu(labels, prompt):
            labels = list(labels)
            return "baby dijon" if menu.SEARCH in labels else labels[0]

        with mock.patch.object(menu, "dmenu", fake_dmenu):
            menu.main_menu()
        self.assertIn("Dijon", wait_until_playing("Dijon") or "")
        self.assertEqual(player.playerctl("status"), "Playing")

    def test_repeat_cycles_through_menu(self):
        player.play(spotify.search(QUERY)["tracks"][0]["uri"])
        player.set_setting("loop", "None")

        # pick the repeat entry in the main menu three times
        def fake_dmenu(labels, prompt):
            return next(label for label in labels if "Repeat:" in label)

        modes = []
        for _ in range(3):
            with mock.patch.object(menu, "dmenu", fake_dmenu):
                menu.main_menu()
            modes.append(player.repeat_mode())
        self.assertEqual(modes, ["all", "one", "off"])

    def test_play_album_then_track_while_playing(self):
        album = spotify.search("discovery daft punk")["albums"][0]
        album_track_names = {track["name"] for track in spotify.album_tracks(album["id"])}
        player.play(album["uri"])
        self.assertIn(player.playerctl("metadata", "--format", "{{title}}"), album_track_names)

        track = spotify.search(QUERY)["tracks"][0]
        player.play(track["uri"])
        self.assertIn(track["name"], player.now_playing())

    def test_shuffle_album(self):
        album = spotify.search("discovery daft punk")["albums"][0]
        player.play(album["uri"], shuffle=True)
        self.assertEqual(player.playerctl("shuffle"), "On")
        self.assertEqual(player.playerctl("status"), "Playing")

    def test_play_liked_songs(self):
        # start from a track that isn't the first liked song, so we can see the switch
        player.play(spotify.search(QUERY)["tracks"][0]["uri"])
        before = player.now_playing()
        player.play(cache.liked_songs_uri())
        self.assertEqual(player.playerctl("status"), "Playing")
        self.assertNotEqual(player.now_playing(), before)


if __name__ == "__main__":
    unittest.main()
