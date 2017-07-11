#!/bin/bash
# Call script from transmission when torrent has completed
export PATH="$PATH:/usr/local/bin"

base_folder=""
complete_folder=""
temp_folder=""
torrent="$TR_TORRENT_DIR/$TR_TORRENT_NAME";

echo "Checking for rar in $torrent"
find $torrent -name "*.rar" -exec unrar e "{}" ${complete_folder} \;

if [ $? -ne 0]; then
  echo "Failed to unpack rar."
  exit $?
fi

# check complete folder for files and place them in the correct folders
for filename in $temp_folder; do
  echo "Checking ${filename}"
  rel_path=$(guess_path.py "${filename}")

  if [ $? -eq 0]; then
    echo "Moving ${filename} to ${base_folder}/${rel_path}"
    mkdir -p "${base_folder}/${rel_path}" && mv "${filename}" "${base_folder}/${rel_path}"
  fi
done

