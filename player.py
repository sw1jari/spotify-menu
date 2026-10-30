"""The official Spotify client, run hidden on a virtual display and controlled over MPRIS.

Spotify's Web API can't start playback on the desktop client and librespot players
get refused by Spotify for many accounts, so playback goes through playerctl.
"""

import shutil
import subprocess
import time

START_WAIT_SECONDS = 30
# the client ignores commands for a moment after it shows up on D-Bus
READY_DELAY_SECONDS = 3
OPEN_ATTEMPTS = 3
OPEN_WAIT_SECONDS = 4
SETTING_WAIT_SECONDS = 8
# fixed id so the starting notification can be closed again
STARTING_NOTIFICATION_ID = "48213"
# MPRIS loop status to the names Spotify shows
REPEAT_MODES = {"None": "off", "Playlist": "all", "Track": "one"}


class PlayerError(Exception):
    pass


def playerctl(*args):
    result = subprocess.run(["playerctl", "-p", "spotify", *args],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def is_running():
    return playerctl("status") is not None


def start():
    """Start the client on a virtual X display, so it never opens a window."""
    if is_running():
        return
    subprocess.Popen(["xvfb-run", "-a", "spotify"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    dunstify("-a", "spotify-menu", "-t", "0", "-r", STARTING_NOTIFICATION_ID,
             "Spotify", "Starting Spotify")
    try:
        for _ in range(START_WAIT_SECONDS):
            time.sleep(1)
            if is_running():
                time.sleep(READY_DELAY_SECONDS)
                return
        raise PlayerError("The hidden Spotify client did not start")
    finally:
        dunstify("-C", STARTING_NOTIFICATION_ID)


def dunstify(*args):
    if shutil.which("dunstify"):
        subprocess.run(["dunstify", *args], stderr=subprocess.DEVNULL)


def current_track_id():
    # mpris gives /com/spotify/track/<id>
    track_path = playerctl("metadata", "mpris:trackid") or ""
    return track_path.rsplit("/", 1)[-1]


def current_track_uri():
    """Uri of the current track, None for an episode, ad or nothing loaded."""
    track_id = current_track_id()
    if not track_id or "/track/" not in (playerctl("metadata", "mpris:trackid") or ""):
        return None
    return f"spotify:track:{track_id}"


def wait_until_started(uri, previous_track_id):
    """True once the client plays the opened uri, False if it ignored the open."""
    deadline = time.time() + OPEN_WAIT_SECONDS
    while time.time() < deadline:
        # the track id is briefly empty while the client switches
        track_id = current_track_id()
        if playerctl("status") == "Playing" and track_id:
            # for a track we can check its id, for a playlist or album only that the track changed
            if uri.startswith("spotify:track:"):
                if uri.endswith(track_id):
                    return True
            elif track_id != previous_track_id:
                return True
        time.sleep(0.2)
    return False


def open_uri(uri):
    """Open a uri, trying again when the client ignores it, which it sometimes does."""
    previous_track_id = current_track_id()
    for _ in range(OPEN_ATTEMPTS):
        playerctl("open", uri)
        if wait_until_started(uri, previous_track_id):
            return
    if playerctl("status") != "Playing":
        raise PlayerError("Spotify did not start playing, try again")


def play(uri, shuffle=False):
    """Play a track, album, playlist, artist or liked songs uri."""
    start()
    open_uri(uri)

    # the client remembers shuffle per playlist and album, so it can only be set after opening
    if shuffle:
        set_shuffle(True)
        first_track_id = current_track_id()
        for _ in range(OPEN_ATTEMPTS):
            playerctl("next")
            time.sleep(1)
            if current_track_id() != first_track_id:
                break
    else:
        set_shuffle(False)


def set_setting(name, wanted):
    """Set shuffle or loop and wait until the client takes it, which can take a few seconds.

    Always waiting means no change is left pending, which would make the next read wrong.
    """
    if playerctl(name) == wanted:
        return
    playerctl(name, wanted)
    deadline = time.time() + SETTING_WAIT_SECONDS
    while time.time() < deadline and playerctl(name) != wanted:
        time.sleep(0.2)


def set_shuffle(enabled):
    set_setting("shuffle", "On" if enabled else "Off")


def repeat_mode():
    """'off', 'all' or 'one', from MPRIS's None, Playlist or Track loop status."""
    return REPEAT_MODES.get(playerctl("loop"), "off")


def cycle_repeat():
    """Go from repeat off to repeat all to repeat one and back to off."""
    modes = list(REPEAT_MODES.values())
    next_mode = modes[(modes.index(repeat_mode()) + 1) % len(modes)]
    loop_status = next(status for status, mode in REPEAT_MODES.items() if mode == next_mode)
    set_setting("loop", loop_status)


def now_playing():
    """'Artist - Title' of the current track, or None when nothing is loaded."""
    if playerctl("status") in (None, "Stopped"):
        return None
    return playerctl("metadata", "--format", "{{artist}} - {{title}}")


def toggle_pause():
    playerctl("play-pause")


def next_track():
    playerctl("next")


def previous_track():
    playerctl("previous")


def toggle_shuffle():
    set_shuffle(playerctl("shuffle") != "On")


def quit():
    subprocess.run(["pkill", "-x", "spotify"])
