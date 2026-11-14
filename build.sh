#!/bin/sh
# Builds the release ZIP from the last commit: only what buyers need (no tests, no docs/).
# Usage: ./build.sh   (commit first; uncommitted changes are not included)
set -e
cd "$(dirname "$0")"
python3 -m unittest discover tests
VERSION=$(python3 -c "import json; print(json.load(open('skills/outbound-core/config.json'))['kit_version'])")
OUT="dist/claude-outbound-kit-$VERSION.zip"
mkdir -p dist
rm -f "$OUT"
git archive --format=zip --prefix=claude-outbound-kit/ -o "$OUT" HEAD README.md INSTALL.md SETUP.md skills
echo "built $OUT"
