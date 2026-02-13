#!/bin/bash

# This script converts SVGs to PNGs as a safety measure for backends 
# that do not support SVG natively or render it incorrectly.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/generated/png"

mkdir -p "$TARGET_DIR"

echo "Converting SVGs to PNGs..."

# We use the same docker image as it contains rsvg-convert (usually)
# If not, this is a placeholder to show where the logic goes.
docker run --rm \
  -v "$SCRIPT_DIR":/documents \
  asciidoctor/docker-asciidoctor \
  /bin/bash -c "for f in generated/*.svg; do rsvg-convert -f png -o \"generated/png/\$(basename \"\$f\" .svg).png\" \"\$f\"; done"

if [ $? -eq 0 ]; then
  echo "Conversion successful! PNGs are in thesis/generated/png/"
else
  echo "Conversion failed! Ensure SVGs exist in thesis/generated/"
  exit 1
fi
