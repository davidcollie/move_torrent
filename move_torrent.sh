#!/bin/bash
# Call script from transmission when torrent has completed
base_folder=""
temp_folder=""

find /$TR_TORRENT_DIR/$TR_TORRENT_NAME -name "*.rar" -execdir nice -n 15 unrar e ${temp_folder} -o- "{}" \;

if [ $? -ne 0]; then
	echo "No torrent to unrar or failed to unpack rar."
	exit 0
fi

# check complete folder for files and place them in the correct folders
for filename in $temp_folder; do
	rel_path="$(./guess_path.py ${filename})"

	if [ $? -eq 0]; then
		mkdir -p ${base_folder}/${rel_path}
		mv filename ${base_folder}/${rel_path}
	fi
done

