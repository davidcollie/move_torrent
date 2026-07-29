#!/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/Users/dave/bin

base_folder="/Users/dave/Downloads/"
temp_folder="/Users/dave/Downloads/media/complete/*"

# check complete folder for files and place them in the correct folders
shopt -s nullglob dotglob
for filename in $temp_folder; do
  rel_path=$(guess_path.py "${filename}")

  if [ $? -eq 0 ]; then
    mkdir -p "${base_folder}/${rel_path}" && mv "${filename}" "${base_folder}/${rel_path}"
  fi
done
