# move_torrent

Scripts that post-process finished torrents into a tidy TV/movie library using
[guessit](https://github.com/guessit-io/guessit).

## Pipeline

1. **`unpack_torrent.sh`** — run by Transmission as its "torrent done" script
   (`TR_TORRENT_DIR` / `TR_TORRENT_NAME`). It skips `sample`/`xxx`, extracts `.rar`
   archives with `unrar`, and stages video files into the completed folder. Direct
   downloads that don't need extracting are **hardlinked** into place (same volume),
   so they don't take up disk space twice while the torrent seeds.
2. **`move_torrent.sh`** — run every 10 minutes from a launchd agent. It scans the
   completed folder and, for each staged file, asks `guess_path.py` where it belongs,
   then moves it into the library.
3. **`guess_path.py`** — runs guessit on a filename and prints the relative
   destination (`tv/Show/Season NN/` or `movies/Title (Year)/`).

## Install

Point Transmission's "done" script at `unpack_torrent.sh` and load a launchd agent
that runs `move_torrent.sh` on an interval. The scripts use hardcoded paths for the
torrents / completed / library folders — edit them to match your setup.

Requires `unrar` and Python 3 with the `guessit` module.
