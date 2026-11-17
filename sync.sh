#!/bin/bash

# Check if IP address is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <raspberry_pi_ip>"
  exit 1
fi

# Variables
SOURCE_DIR=$(pwd)  # Current directory
CURRENT_FOLDER_NAME=$(basename "$SOURCE_DIR")  # Name of the current folder
TARGET_DIR="mda@$1:/home/mda/repos/$CURRENT_FOLDER_NAME"  # Path on Raspberry Pi
EXCLUDE_DIRS=("venv" ".idea" "__pycache__" "picarro_data")  # Directories to exclude

# Build the rsync exclude options
EXCLUDE_OPTIONS=""
for dir in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_OPTIONS+="--exclude=$dir "
done

# rsync command
eval rsync -av $EXCLUDE_OPTIONS "$SOURCE_DIR/" "$TARGET_DIR"