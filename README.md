# spotify-menu

A dmenu frontend for Spotify that never shows the Spotify window. From one menu you can play your playlists, your liked songs, or anything you search for, and pause, skip or toggle shuffle while something is playing.

It browses your library with the Spotify Web API. Playback goes through the official Spotify client, started hidden on a virtual X display (Xvfb) and controlled with `playerctl`. Your media keys keep working with it.

Why not the Web API or spotifyd for playback? The Web API returns server errors when asked to start the desktop client, and Spotify currently refuses audio keys to librespot based players such as spotifyd for many accounts.

## Requirements
python 3.9+, dmenu, playerctl, xorg-server-xvfb, the Spotify desktop client, xclip (optional, to offer a copied client id). Creating a developer app needs Spotify Premium. Errors show as a notification through `dunstify`, or `notify-send` when dunst isn't installed.

## Setup
1. Create an app at https://developer.spotify.com/dashboard. Select the Web API, and add `http://127.0.0.1:8888/callback` as a redirect URI.
2. Install by symlinking the script; the Python modules are found next to it:
   ```sh
   ln -s "$PWD/spotify-menu" ~/.local/bin/spotify-menu
   ```
3. Run `spotify-menu`. The first time, it asks for your app's client id in dmenu (a copied client id is offered directly, or paste with Ctrl+Shift+Y) and opens the browser to log in. The token is saved in `~/.config/spotify-menu/` and refreshes itself. From a terminal, `spotify-menu login YOUR_CLIENT_ID` does the same.

The Spotify client itself must have been logged in once, which happens the first time you open it normally.

## Usage
Run `spotify-menu`, ideally from a keybinding. Typing anything that isn't an entry searches for it, also on the search results to search again. Press Escape to go back a level. While a song plays, "♡ Like" adds it to your liked songs and "♥ Unlike" removes it again. "➕ Add to playlist" adds it to one of your own or collaborative playlists, unless it's in there already. "⏹ Quit Spotify" closes the hidden client.

Playlists, albums and liked songs can be played or shuffled as a whole. "▶ Play" continues where you left off in that playlist, which is how the Spotify client handles it. Picking a single track plays only that track, since the client can't be told to start a playlist at a given track. Spotify only lets apps list the tracks of playlists you own or collaborate on.

In search, ♥ marks your own liked songs that match, then ♪ tracks (up to 30), 👤 artists, 💿 albums and 📃 playlists (up to 10 each). Spotify's ranking for apps is weak, so adding the artist helps: "baby dijon" rather than "baby".

Your playlists and liked songs are cached in `~/.cache/spotify-menu/`, so the menu opens instantly. Each time it opens, the cache is refreshed in the background (at most once a minute) with `spotify-menu refresh`.

While the hidden client runs, starting Spotify normally won't open a window, since Spotify only runs one instance. Quit the hidden one first.

## Tests
```sh
python3 -m unittest
```
The tests run against your real account, so log in first. They start the hidden client and play a few tracks for a couple of seconds each, then pause.
