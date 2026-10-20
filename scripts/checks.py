"""Integrity checks on the rebuilt register.

Usage: python3 -I checks.py <data_dir>
"""
import json, random, re, sys, unicodedata
from collections import Counter, defaultdict

d = sys.argv[1]
base = json.load(open(f"{d}/baseline_1280.json"))
reg = json.load(open(f"{d}/register.json"))
changes = json.load(open(f"{d}/changes.json"))
notes = json.load(open(f"{d}/tsb_notes.json"))
btxt = open(f"{d}/baseline_1280.txt", encoding="utf-8").read()


def n(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()


# A. every baseline code+name pair appears in the PDF text (first 2 words of name near the code)
lines = btxt.splitlines()
miss = []
idx = defaultdict(list)
for i, ln in enumerate(lines):
    for m in re.finditer(r"(?<!\d)(\d{3}) (\d{2,3})(?!\d)", ln):
        idx[(m.group(1), m.group(2))].append(i)
for c in base["codes"]:
    words = n(c["network"]).split()[:2]
    hits = idx.get((c["mcc"], c["mnc"]), [])
    ok = False
    for i in hits:
        window = n(" ".join(lines[max(0, i - 2):i + 3]))
        if all(w in window for w in words):
            ok = True; break
    if not ok:
        miss.append((c["mcc"], c["mnc"], c["country"], c["network"]))
print(f"A. baseline pairs not confirmed in PDF text: {len(miss)} of {len(base['codes'])}")
for m in miss[:15]:
    print("   ", m)

# B. TSB notes on 901/991 vs amendment entries
amend_codes = defaultdict(list)
for ch in changes:
    amend_codes[f"{ch['mcc']} {ch['mnc']}"].append((ch["issue"], ch["op"]))
print("B. TSB notes on shared codes:")
for nt in notes:
    if nt["kind"] == "extra_territorial":
        continue
    for code in nt["codes"]:
        am = amend_codes.get(code, [])
        near = [a for a in am if abs(a[0] - nt["issue"]) <= 4]
        print(f"   note OB {nt['issue']} {nt['kind']:20s} {code}: amendments nearby {near or 'NONE'}")

# C. leftover artefacts in names
bad = [r for r in reg if re.search(r"\b(ADD|SUP|LIR)\b|\*|\b\d{3} \d{2,3}\b|Country|Geographical|^\W|\s$", r["network"])]
print("C. names with possible artefacts:", len(bad))
for r in bad[:20]:
    print("   ", r["mcc"], r["mnc"], r["country"], "|", r["network"])
empty = [r for r in reg if not r["network"].strip()]
print("   empty names:", len(empty))

# D. MNC length mix within an MCC
lens = defaultdict(Counter)
for r in reg:
    lens[r["mcc"]][len(r["mnc"])] += 1
mixed = {m: dict(c) for m, c in lens.items() if len(c) > 1}
print("D. MCCs mixing 2- and 3-digit MNCs:", mixed)
for m in mixed:
    minority = min(mixed[m], key=mixed[m].get)
    ex = [(r["mnc"], r["network"], r["history"][-1]["issue"]) for r in reg if r["mcc"] == m and len(r["mnc"]) == minority]
    print("   ", m, "minority length", minority, ex[:6])

# E. random sample of changes for eye-check
random.seed(1348)
print("E. random sample of 12 changes:")
for ch in random.sample(changes, 12):
    print(f"   OB {ch['issue']} A{ch['amendment']} {ch['op']} {ch['mcc']} {ch['mnc']} {ch['country']} | {ch['network']} | src={ch['name_source']}")
