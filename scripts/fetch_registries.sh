#!/usr/bin/env bash
# Download the national MNC registries into reg/raw/.
# The UK file (Ofcom) is behind a bot check and is NOT fetched here; see RUNBOOK.md.
# Exits non-zero if any registry fails, after trying all of them.
set -u
root="$1"; raw="$root/reg/raw"; mkdir -p "$raw"
fail=0
dl() {  # dl <file> <url>
  local code
  code=$(curl -sSL --retry 2 -A "Mozilla/5.0" -o "$raw/$1.tmp" -w '%{http_code}' --max-time 120 "$2")
  if [ "$code" = "200" ] && [ -s "$raw/$1.tmp" ]; then mv "$raw/$1.tmp" "$raw/$1"; echo "ok   $1"
  else rm -f "$raw/$1.tmp"; echo "FAIL $1 ($code) $2"; fail=1; fi
}
dl us_hni.html  "https://imsiadmin.com/assignments/hni/"
dl us_cbrs.html "https://imsiadmin.com/assignments/cbrs/"
dl ca_cnac.html "https://cnac.ca/data/MNC_Codes.htm"
dl bnetza_imsi.pdf "https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Nummerierung/IMSI/DL/imsi_zugbloecke.html"
dl hk_mnc.csv   "https://www.ofca.gov.hk/filemanager/ofca/common/datagovhk/mnc_en_sc.csv"
dl nl_nummers.zip "https://www.acm.nl/sites/default/files/registers/nummers_csv.zip"
if [ -s "$raw/nl_nummers.zip" ]; then mkdir -p "$raw/nl" && unzip -o -q "$raw/nl_nummers.zip" -d "$raw/nl" || fail=1; fi
python3 -I "$root/scripts/fetch_fi.py" "$raw/fi_eserv.html" "$raw/fi_mnc.csv" >/dev/null && echo "ok   fi_mnc.csv" || { echo "FAIL fi_mnc.csv"; fail=1; }
# US list: table rows to JSON for the parser
python3 -I - "$raw" <<'PY' || fail=1
import html, json, re, sys
raw = sys.argv[1]
t = open(f"{raw}/us_hni.html", encoding="utf-8", errors="replace").read()
rows = [[html.unescape(re.sub(r"<.*?>", "", c)).strip() for c in re.findall(r"<t[dh].*?</t[dh]>", r, flags=re.S | re.I)]
        for r in re.findall(r"<tr.*?</tr>", t, flags=re.S | re.I)]
rows = [r for r in rows if r and re.match(r"3\d\d-\d{3}", r[0])]
assert len(rows) > 400, f"US list looks truncated: {len(rows)} rows"
json.dump(rows, open(f"{raw}/us_hni_rows.json", "w"))
print("ok   us_hni_rows.json", len(rows))
PY
exit $fail
