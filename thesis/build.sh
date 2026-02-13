#!/bin/bash

set -euo pipefail

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building thesis PDF via Docker..."

# Ensure the generated directory exists
mkdir -p "$SCRIPT_DIR/generated"

echo "Generating charts..."
python3 "$SCRIPT_DIR/generate_charts.py"

PROBE_THEME="$SCRIPT_DIR/.theme-probe.yml"
RUNTIME_THEME="$SCRIPT_DIR/.theme-runtime.yml"
PROBE_PDF="$SCRIPT_DIR/main.probe.pdf"
PROBE_TEXT="$SCRIPT_DIR/.main.probe.txt"
BUNDLE_CACHE_DIR="$SCRIPT_DIR/.asciidoctor-bundle"

create_theme_with_start_at() {
  local input_theme="$1"
  local output_theme="$2"
  local start_at_value="$3"

  python3 - "$input_theme" "$output_theme" "$start_at_value" <<'PY'
import pathlib
import re
import sys

input_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
start_at = sys.argv[3]

content = input_path.read_text(encoding='utf-8')
updated, count = re.subn(
    r'(^\s*start-at:\s*).*$','\\g<1>' + start_at,
    content,
    count=1,
    flags=re.MULTILINE,
)

if count == 0:
    raise SystemExit('Could not find page.numbering.start-at in theme.yml')

output_path.write_text(updated, encoding='utf-8')
PY
}

build_pdf_with_theme() {
  local theme_file="$1"
  local output_pdf="$2"

  mkdir -p "$BUNDLE_CACHE_DIR"

  docker run --rm \
    -v "$SCRIPT_DIR":/documents \
    -v "$BUNDLE_CACHE_DIR":/usr/local/bundle \
    asciidoctor/docker-asciidoctor \
    /bin/bash -c "if ! gem list -i asciidoctor-lists >/dev/null 2>&1; then gem install --no-document --quiet asciidoctor-lists >/dev/null; fi && \
    asciidoctor-pdf \
    -r asciidoctor-bibtex \
    -r asciidoctor-mathematical \
    -r asciidoctor-lists \
    -a pdf-theme=$(basename "$theme_file") \
    -o $(basename "$output_pdf") \
    main.adoc"
}

echo "Calibrating page numbering so Einleitung starts at 1..."
# We do a probe build first because Asciidoctor PDF cannot dynamically start arabic
# page numbering at the first real chapter. The probe detects the page where
# "1. Einleitung" appears, then the final build sets start-at to that offset.
create_theme_with_start_at "$SCRIPT_DIR/theme.yml" "$PROBE_THEME" "body"
build_pdf_with_theme "$PROBE_THEME" "$PROBE_PDF"

if command -v pdftotext >/dev/null 2>&1; then
  pdftotext "$PROBE_PDF" "$PROBE_TEXT"
  INTRO_START_AT=$(python3 - "$PROBE_TEXT" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
pages = text.split('\f')

intro_page_number = None
for page in pages:
  if re.search(r'(?m)^\s*1\.\s+Einleitung\s*$', page):
        numbers = re.findall(r'(?m)^\s*(\d+)\s*$', page)
        if numbers:
            intro_page_number = int(numbers[-1])
        break

print(intro_page_number or 1)
PY
)
else
  echo "Warning: pdftotext not found, falling back to start-at=3"
  INTRO_START_AT=3
fi

echo "Using page.numbering.start-at=$INTRO_START_AT"
create_theme_with_start_at "$SCRIPT_DIR/theme.yml" "$RUNTIME_THEME" "$INTRO_START_AT"

echo "Building final thesis PDF..."
build_pdf_with_theme "$RUNTIME_THEME" "$SCRIPT_DIR/main.pdf"

rm -f "$PROBE_THEME" "$RUNTIME_THEME" "$PROBE_PDF" "$PROBE_TEXT"

if [ $? -eq 0 ]; then
  echo "Build successful! PDF created at thesis/main.pdf"
else
  echo "Build failed!"
  exit 1
fi
