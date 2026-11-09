#!/usr/bin/env bash
# Restores an archive kept on a GitHub release (the workflows keep their state there, not in the code history).
# Usage: restore-release.sh TAG FILE DEST [member patterns...]
# Downloads FILE, or the spare copy uploaded just before it (see save-release.sh), and unpacks it into DEST, only the
# members matching the patterns when given. Exits 1 when neither copy can be had: each workflow decides what that means.
set -uo pipefail
tag=$1 file=$2 dest=$3
shift 3
gh release download "$tag" --pattern "$file" --dir "$RUNNER_TEMP" --clobber \
  || { gh release download "$tag" --pattern "spare-$file" --dir "$RUNNER_TEMP" --clobber \
       && mv "$RUNNER_TEMP/spare-$file" "$RUNNER_TEMP/$file"; } \
  || exit 1
mkdir -p "$dest"
if [ $# -gt 0 ]; then tar -xzf "$RUNNER_TEMP/$file" -C "$dest" --wildcards "$@"; else tar -xzf "$RUNNER_TEMP/$file" -C "$dest"; fi
