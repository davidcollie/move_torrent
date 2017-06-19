#!/bin/bash
# Call script from transmission when torrent has completed
base_folder=""
complete_folder=""
temp_folder=""

echo "Checking for rar in ${TR_TORRENT_DIR}"
find $TR_TORRENT_DIR -name "*.rar" -exec unrar e "{}" ${complete_folder} \;

if [ $? -ne 0]; then
  echo "No torrent to unrar or failed to unpack rar."
  exit $?
fi

# check complete folder for files and place them in the correct folders
for filename in $temp_folder; do
  echo "Checking ${filename}"
  rel_path=$(./guess_path.py "${filename}")

  if [ $? -eq 0]; then
    echo "Moving ${filename} to ${base_folder}/${rel_path}"
    mkdir -p "${base_folder}/${rel_path}" && mv "${filename}" "${base_folder}/${rel_path}"
  fi
done

