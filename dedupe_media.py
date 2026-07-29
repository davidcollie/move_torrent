#!/usr/bin/env python3
"""De-duplicate media between the torrents folder and the media library.

Older torrents were *copied* into the library instead of hardlinked, so a file
that is still seeding exists as two full copies on the same volume. This one-off
tool walks the torrents folder, finds each copy in the media library, and — after
prompting — replaces the library copy with a hardlink back to the torrent file,
reclaiming the duplicated space while keeping both paths working.

A torrent file is matched to its library copy by basename + identical size + same
device + different inode, then a content check (head/tail chunks, or --full-hash).
The replace is atomic: the torrent file always holds the data, so there is no
data-loss window. Already-hardlinked pairs are detected and skipped, so the script
is idempotent and safe to re-run.
"""

import argparse
import hashlib
import os
import stat
import sys
from pathlib import Path

TORRENTS = Path.home() / "Downloads" / "torrents"
MEDIA = Path.home() / "Downloads" / "media"
COMPLETE_DIRNAME = "complete"  # staging dir under MEDIA, excluded from the library index

VIDEO_EXTS = {".avi", ".mp4", ".mkv", ".m4v", ".mov", ".ts", ".wmv"}
SKIP_SUBSTRINGS = ("sample", "xxx")
CHUNK = 4 * 1024 * 1024  # head/tail bytes compared in the quick content check


def is_skippable_name(name: str) -> bool:
    low = name.lower()
    return any(s in low for s in SKIP_SUBSTRINGS)


def human(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024:
            return f"{x:.2f} {unit}"
        x /= 1024
    return f"{x:.2f} TB"


def sha256(path: str) -> bytes:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.digest()


def same_content(a: str, b: str, size: int, full_hash: bool) -> bool:
    """Cheap-but-strong duplicate check. Sizes are already known equal."""
    if full_hash:
        return sha256(a) == sha256(b)
    with open(a, "rb") as fa, open(b, "rb") as fb:
        if fa.read(CHUNK) != fb.read(CHUNK):
            return False
        if size > CHUNK:
            off = size - CHUNK
            fa.seek(off)
            fb.seek(off)
            if fa.read(CHUNK) != fb.read(CHUNK):
                return False
    return True


def build_library_index(movies_only: bool) -> dict:
    """Map basename -> list of (path, os.stat_result) for regular files in the library."""
    index: dict[str, list] = {}
    roots = [MEDIA / "movies"] if movies_only else [MEDIA]
    for base in roots:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            # never descend into the staging folder
            if Path(root) == MEDIA:
                dirs[:] = [d for d in dirs if d != COMPLETE_DIRNAME]
            for name in files:
                p = os.path.join(root, name)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
                    continue  # skip symlinks / non-regular
                index.setdefault(name, []).append((p, st))
    return index


def scan(index: dict, full_hash: bool):
    """Return (actions, counters). actions = list of (torrent_path, library_path, size)."""
    actions = []
    counts = {
        "torrent_videos": 0,
        "already_linked": 0,
        "size_mismatch": 0,
        "content_mismatch": 0,
        "ambiguous": 0,
        "no_match": 0,
    }
    for root, _, files in os.walk(TORRENTS):  # followlinks=False: don't chase dir symlinks
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in VIDEO_EXTS or is_skippable_name(name):
                continue
            counts["torrent_videos"] += 1
            tpath = os.path.join(root, name)
            try:
                tst = os.lstat(tpath)
            except OSError:
                continue
            if not stat.S_ISREG(tst.st_mode) or stat.S_ISLNK(tst.st_mode):
                continue

            candidates = [
                (p, st) for (p, st) in index.get(name, [])
                if st.st_dev == tst.st_dev
            ]
            if not candidates:
                counts["no_match"] += 1
                continue
            if any(st.st_ino == tst.st_ino for _, st in candidates):
                counts["already_linked"] += 1
                continue

            size_matches = [(p, st) for (p, st) in candidates if st.st_size == tst.st_size]
            if not size_matches:
                counts["size_mismatch"] += 1
                print(f"  skip (size differs): {name}")
                continue
            if len(size_matches) > 1:
                counts["ambiguous"] += 1
                print(f"  skip (ambiguous, {len(size_matches)} library matches): {name}")
                for p, _ in size_matches:
                    print(f"        {p}")
                continue

            lib_path, _ = size_matches[0]
            if not same_content(tpath, lib_path, tst.st_size, full_hash):
                counts["content_mismatch"] += 1
                print(f"  skip (content differs): {name}")
                continue

            actions.append((tpath, lib_path, tst.st_size))
    return actions, counts


def replace_with_hardlink(torrent_path: str, library_path: str) -> None:
    """Atomically replace the library copy with a hardlink to the torrent file."""
    tmp = library_path + ".deduptmp"
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.link(torrent_path, tmp)          # hardlink to the torrent inode
    try:
        os.replace(tmp, library_path)   # atomic swap; frees the old copy's blocks
    except OSError:
        if os.path.lexists(tmp):
            os.remove(tmp)
        raise
    if os.stat(library_path).st_ino != os.stat(torrent_path).st_ino:
        raise RuntimeError(f"post-check failed: inodes differ for {library_path}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("-n", "--dry-run", action="store_true",
                    help="scan and report only; make no changes and don't prompt")
    ap.add_argument("--full-hash", action="store_true",
                    help="verify duplicates with a full sha256 instead of head/tail chunks")
    ap.add_argument("--movies-only", action="store_true",
                    help="only de-dupe under media/movies (default: all media)")
    args = ap.parse_args()

    if not TORRENTS.is_dir() or not MEDIA.is_dir():
        print(f"error: expected {TORRENTS} and {MEDIA} to exist (is the volume mounted?)",
              file=sys.stderr)
        return 2

    print(f"Indexing library{' (movies only)' if args.movies_only else ''} ...")
    index = build_library_index(args.movies_only)
    print(f"Scanning {TORRENTS} for duplicates "
          f"({'full sha256' if args.full_hash else 'head/tail'} content check) ...\n")
    actions, counts = scan(index, args.full_hash)

    total_bytes = sum(sz for _, _, sz in actions)
    print(f"\nScanned {counts['torrent_videos']} torrent video file(s).")
    print(f"  duplicates to reclaim : {len(actions)}  ({human(total_bytes)})")
    print(f"  already hardlinked    : {counts['already_linked']}")
    print(f"  no library copy       : {counts['no_match']}")
    print(f"  size mismatch (kept)  : {counts['size_mismatch']}")
    print(f"  content mismatch(kept): {counts['content_mismatch']}")
    print(f"  ambiguous (kept)      : {counts['ambiguous']}")

    if not actions:
        print("\nNothing to do.")
        return 0

    if args.dry_run:
        print("\n[dry-run] would replace these library copies with hardlinks:")
        for _, lib, sz in actions:
            print(f"  {human(sz):>10}  {lib}")
        print(f"\n[dry-run] total reclaimable: {human(total_bytes)}")
        return 0

    print("\nFor each duplicate: [y]es  [N]o/skip  [a]ll remaining  [q]uit\n")
    reclaimed = 0
    done = 0
    auto = False
    for i, (tpath, lib, sz) in enumerate(actions, 1):
        tino = os.stat(tpath).st_ino
        try:
            lino = os.stat(lib).st_ino
        except OSError:
            print(f"  [{i}/{len(actions)}] library file vanished, skipping: {lib}")
            continue
        print(f"[{i}/{len(actions)}] {os.path.basename(lib)}  ({human(sz)})")
        print(f"    torrent: {tpath}  (inode {tino})")
        print(f"    library: {lib}  (inode {lino})")
        print(f"    -> hardlink library to torrent, reclaiming {human(sz)}")

        if not auto:
            try:
                ans = input("    Proceed? [y/N/a/q] ").strip().lower()
            except EOFError:
                print("\nno input; quitting.")
                break
            if ans == "q":
                break
            if ans == "a":
                auto = True
            elif ans != "y":
                print("    skipped.\n")
                continue

        try:
            replace_with_hardlink(tpath, lib)
            reclaimed += sz
            done += 1
            print(f"    linked. reclaimed {human(sz)}.\n")
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"    ERROR: {e}\n", file=sys.stderr)

    print(f"Done. De-duped {done} file(s), reclaimed {human(reclaimed)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
