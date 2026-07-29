#!/bin/bash

# Extend PATH for tools like unrar
export PATH="$PATH:/usr/local/bin"

# Logging
LOGFILE="/tmp/transmission_postprocess.log"
echo "$(date): Script started for torrent '$TR_TORRENT_NAME' in '$TR_TORRENT_DIR'" >> "$LOGFILE"

# Paths
complete_folder="/Users/dave/Downloads/media/complete"
torrent_path="$TR_TORRENT_DIR/$TR_TORRENT_NAME"

# Check for unwanted content in name (case-insensitive)
if echo "$torrent_path" | grep -Eiq "(sample|xxx)"; then
    echo "$(date): Skipping due to matched pattern in path: $torrent_path" >> "$LOGFILE"
    exit 0
fi

# Function to process individual files
process_file() {
    local f="$1"
    filename="$(basename "$f")"

    # Skip file if name contains "sample" or "xxx"
    if echo "$filename" | grep -Eiq "(sample|xxx)"; then
        echo "$(date): Skipping file due to pattern match: $f" >> "$LOGFILE"
        return
    fi

    ext="${f##*.}"
    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    case "$ext_lower" in
        rar)
            echo "$(date): Extracting RAR archive: $f" >> "$LOGFILE"
            unrar e -o+ "$f" "$complete_folder" >> "$LOGFILE" 2>&1
            ;;
        avi|mp4|mkv|m4v|mov|ts|wmv)
            # No extraction needed: hardlink into the completed folder instead of
            # copying, so the file doesn't occupy disk space twice while seeding.
            # torrents/ and media/ share one volume, so the hardlink is free.
            dest="$complete_folder/$filename"
            if [ -e "$dest" ] || [ -L "$dest" ]; then
                echo "$(date): Already staged, skipping: $dest" >> "$LOGFILE"
            elif ln "$f" "$dest" 2>>"$LOGFILE"; then
                echo "$(date): Hardlinked video file: $f -> $dest" >> "$LOGFILE"
            else
                # Safety net only (e.g. torrents/ and media/ on different volumes,
                # where a hardlink can't cross). Falls back to the old copy behavior.
                echo "$(date): Hardlink failed; copying instead: $f" >> "$LOGFILE"
                cp -n "$f" "$complete_folder"
            fi
            ;;
        *)
            echo "$(date): Skipping unsupported file: $f" >> "$LOGFILE"
            ;;
    esac
}

# Main logic
if [ -d "$torrent_path" ]; then
    # Skip the entire torrent if its folder name includes "sample"
    if echo "$torrent_path" | grep -iq "sample"; then
        echo "$(date): Skipping folder marked as sample: $torrent_path" >> "$LOGFILE"
        exit 0
    fi

    echo "$(date): '$torrent_path' is a directory. Scanning..." >> "$LOGFILE"
    find "$torrent_path" -type f | while IFS= read -r file; do
        process_file "$file"
    done
elif [ -f "$torrent_path" ]; then
    # Skip the file if its name includes "sample"
    if echo "$torrent_path" | grep -iq "sample"; then
        echo "$(date): Skipping file marked as sample: $torrent_path" >> "$LOGFILE"
        exit 0
    fi

    echo "$(date): '$torrent_path' is a file. Processing single file..." >> "$LOGFILE"
    process_file "$torrent_path"
else
    echo "$(date): ERROR — Torrent path not found: $torrent_path" >> "$LOGFILE"
fi
