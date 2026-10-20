"""Checks that must pass before anything is committed. Exits 1 with reasons on failure.

Usage: python3 -I validate.py <repo_root>
"""
import json, os, sys

root = sys.argv[1]
J = lambda p: json.load(open(f"{root}/{p}"))
problems = []

am = J("data/amendments_pdf.json")
got = sorted(a for i in am["issues"] for a in i["amendments"])
if got != list(range(1, max(got) + 1)):
    problems.append(f"amendment numbering broken: missing {sorted(set(range(1, max(got)+1)) - set(got))}, repeated {sorted({a for a in got if got.count(a) > 1})}")
if am.get("orphans"):
    problems.append(f"{len(am['orphans'])} amendment text lines could not be attached to a code: {am['orphans'][:3]}")
undated = [i["issue"] for i in am["issues"] if not i["date"]]
if undated:
    problems.append(f"bulletins with no parsed date: {undated}")
no_head = [(e["issue"], e["mcc"], e["mnc"]) for e in am["entries"] if not e["op"] or not e["country"]]
if no_head:
    problems.append(f"entries without a country heading or operation: {no_head[:5]}")

conf = J("data/conflicts.json")
if conf["conflicts"]:
    problems.append(f"{len(conf['conflicts'])} amendments did not apply cleanly: {[(c['issue'], c['op'], c['mcc'], c['mnc'], c['problem']) for c in conf['conflicts'][:5]]}")
if conf["unknown_countries"]:
    problems.append(f"amendment country names not in the baseline (add to scripts/country_iso.py and geo): {list(conf['unknown_countries'])}")

# Word cross-check where available
dx = J("data/amendments_docx.json")
P = {(e["issue"], e["op"], e["mcc"], e["mnc"]) for e in am["entries"]}
D = {(e["issue"], e["op"], e["mcc"], e["mnc"]) for e in dx["entries"]}
only_d = sorted(D - P)
if only_d:
    problems.append(f"entries in the Word file missing from the PDF parse: {only_d[:5]}")

iso = J("geo/country_iso.json")
names = {r["country"] for r in J("data/register.json") if r["scope"] == "geographic"}
missing_iso = sorted(names - set(iso))
if missing_iso:
    problems.append(f"countries without an ISO mapping (run scripts/country_iso.py and geo/build_geo.mjs): {missing_iso}")

reg = J("reg/registries.json")
from collections import Counter
cnt = Counter(r["registry"] for r in reg["records"] if r["status"] == "assigned")
floor = {"us_imsi": 350, "ca_cnac": 50, "uk_ofcom": 50, "de_bnetza": 25, "hk_ofca": 40, "fi_traficom": 30, "nl_acm": 30}
for k, v in floor.items():
    if cnt.get(k, 0) < v:
        problems.append(f"registry {k} has only {cnt.get(k, 0)} assigned codes (expected at least {v}); the download or parse probably broke")

if problems:
    print("VALIDATION FAILED")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print(f"validation passed: {len(got)} amendments, {len(am['entries'])} entries, registries {dict(cnt)}")
