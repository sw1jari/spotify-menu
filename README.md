# spotify-menu

A dmenu frontend for Spotify that never shows the Spotify window. Play playlists, liked songs or anything you search for, all from one menu.

## Demo

The playlists and songs below are demo data.

**Playing a playlist**, the bar shows what's on

![playing a playlist](docs/spotify-menu-playlist.gif)

**Search**, by typing anything that isn't a menu entry

![searching](docs/spotify-menu-search.gif)

**Playback controls**, pause, next, repeat

![playback controls](docs/spotify-menu-controls.gif)

**Like and add to playlist**

![liking and adding to a playlist](docs/spotify-menu-like.gif)

**Keyboard media keys**, play/pause, next and previous keep working

![keyboard media keys](docs/spotify-menu-mediakeys.gif)

## Features

- Your playlists and liked songs, played or shuffled as a whole
- Search for tracks, artists, albums and playlists, your liked songs first
- Pause, next, previous, shuffle and repeat
- Like or unlike the current song, add it to one of your playlists
- Opens instantly from a cache that refreshes in the background
- A notification while the hidden client starts up

## How it works

| Part | Done with |
|---|---|
| browsing and search | the Spotify Web API |
| playback | the official Spotify client, hidden on a virtual display (Xvfb) |
| controls and media keys | `playerctl` |

The Web API can't start playback on the desktop client, and librespot based players like spotifyd get refused by Spotify for many accounts, hence the hidden client.

## Install

| Needs | For |
|---|---|
| python 3.9+, dmenu | the menu |
| the Spotify desktop client, logged in once | playback |
| playerctl, xorg-server-xvfb | controlling the hidden client |
| a Spotify developer app (needs Premium) | the Web API |
| dunst or notify-send | notifications |
| xclip (optional) | offering a copied client id |

**Create an app** at https://developer.spotify.com/dashboard, select the Web API, and add `http://127.0.0.1:8888/callback` as a redirect URI.

**Link the script**, the Python modules are found next to it:

```sh
ln -s "$PWD/spotify-menu" ~/.local/bin/spotify-menu
```

**Log in** by running `spotify-menu`. It asks for the client id and opens the browser. Or from a terminal:

```sh
spotify-menu login YOUR_CLIENT_ID
```

The token is saved in `~/.config/spotify-menu/` and refreshes itself.

## Usage

Run `spotify-menu`, ideally from a keybinding. Escape goes back a level.

| Entry | What it does |
|---|---|
| ⏯ ⏭ ⏮ | pause/resume, next, previous |
| 🔀 Shuffle, 🔁 Repeat | toggle shuffle, cycle repeat off, all, one |
| ♡ Like / ♥ Unlike | add or remove the current song from liked songs |
| ➕ Add to playlist | add the current song to one of your playlists |
| ⏹ Quit Spotify | close the hidden client |
| 🔍 Search, or just type | search Spotify |
| ♥ Liked songs | play, shuffle or pick from your liked songs |
| 🔄 Refresh library | fetch your playlists right away |
| a playlist name | play, shuffle or pick a track |

Search results are marked ♥ your liked songs, ♪ tracks, 👤 artists, 💿 albums, 📃 playlists. Adding the artist helps, like "baby dijon" rather than "baby".

Good to know:
- ▶ Play resumes a playlist where you left off, like the Spotify app does
- Picking one track plays only that track, the client can't start a playlist at a given track
- Spotify only lists tracks of playlists you own or collaborate on
- While the hidden client runs, opening Spotify normally shows no window, quit the hidden one first

## Tests

```sh
python3 -m unittest
```

The tests use your real account. They start the hidden client and play a few tracks for a couple of seconds each.
