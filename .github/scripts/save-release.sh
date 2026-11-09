#!/usr/bin/env bash
# Saves folders as one archive on a GitHub release, replacing the last one.
# Usage: save-release.sh TAG FILE DIR [paths inside DIR...]
# --clobber deletes the old file before uploading the new one, so an upload that fails halfway would leave nothing.
# The spare copy goes up first: at any moment one complete archive is on the release (restore-release.sh uses either).
set -euo pipefail
tag=$1 file=$2 dir=$3
shift 3
tar -czf "$RUNNER_TEMP/$file" -C "$dir" "$@"
cp "$RUNNER_TEMP/$file" "$RUNNER_TEMP/spare-$file"
gh release upload "$tag" "$RUNNER_TEMP/spare-$file" --clobber
gh release upload "$tag" "$RUNNER_TEMP/$file" --clobber
