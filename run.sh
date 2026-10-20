#!/usr/bin/env bash
# New Networks: mechanical pipeline. Research and cards are done by hand (or by the
# scheduled task) following RUNBOOK.md; this script does everything else.
#
#   ./run.sh setup      install tools (idempotent)
#   ./run.sh fetch      download new bulletins; prints new issue numbers to work/new_issues.txt
#   ./run.sh registries download national registries (UK is separate, see RUNBOOK.md)
#   ./run.sh build      parse, replay, classify, compare, update sightings, validate, build index.html
#   ./run.sh all        fetch + registries + build
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="python3 -I"
cd "$ROOT"
mkdir -p work

setup() {
  command -v pdftotext >/dev/null || { (apt-get update -qq && apt-get install -y -qq poppler-utils) >/dev/null; }
  $PY -c "import docx, lxml, pycountry" 2>/dev/null || pip install -q --break-system-packages python-docx lxml pycountry
  [ -d geo/node_modules/d3-geo ] || (cd geo && npm install --silent --no-audit --no-fund)
  echo "setup ok"
}

fetch() {
  $PY scripts/fetch_bulletins.py "$ROOT" | tee work/new_issues.txt
}

registries() {
  bash scripts/fetch_registries.sh "$ROOT"
}

build() {
  # Word files for any newly fetched bulletins (incremental; older issues are kept from the JSON)
  if ls work/ob/*.docx >/dev/null 2>&1; then $PY scripts/parse_docx_amend.py work/ob data/amendments_docx.json; fi
  $PY scripts/parse_amendments.py data/pdftext data/amendments_pdf.json
  $PY scripts/extract_notes.py data/pdftext data/tsb_notes.json
  $PY scripts/replay.py data/baseline_1280.json data/amendments_pdf.json data/amendments_docx.json data
  $PY scripts/classify.py data/register.json reg/registries.json data/register_typed.json >/dev/null
  # new country names: map them and re-project the map points
  if ! $PY scripts/validate.py "$ROOT" >/dev/null 2>&1 && $PY scripts/validate.py "$ROOT" | grep -q "ISO mapping"; then
    $PY scripts/country_iso.py data/register_typed.json geo/country_iso.json
    (cd geo && node build_geo.mjs country_iso.json geo.json)
  fi
  if [ -f reg/raw/us_hni_rows.json ]; then
    $PY scripts/parse_registries.py reg/raw reg/registries.json
    $PY scripts/compare.py data/register.json reg/registries.json reg/compare.json
  fi
  $PY scripts/update_sightings.py "$ROOT"
  $PY scripts/validate.py "$ROOT"
  $PY scripts/build_atlas.py "$ROOT" scripts/atlas_template.html index.html
}

case "${1:-all}" in
  setup) setup ;;
  fetch) fetch ;;
  registries) registries ;;
  build) build ;;
  all) setup; fetch; registries || echo "WARNING: a registry download failed; see above"; build ;;
  *) echo "usage: $0 setup|fetch|registries|build|all"; exit 2 ;;
esac
