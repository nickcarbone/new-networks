"""Assemble the data bundle for the New Networks atlas page and inject it into the template.

Usage: python3 -I build_atlas.py <nn_root> <template_html> <out_html>
"""
import json, re, sys, datetime
from collections import Counter

root, tpl, out = sys.argv[1:4]
D = lambda p: json.load(open(f"{root}/{p}"))

typed = D("data/register_typed.json")
reg = typed["register"]
changes = D("data/changes.json")
notes = D("data/tsb_notes.json")
issues = D("data/amendments_pdf.json")["issues"]
cmp = D("reg/compare.json")
iso = D("geo/country_iso.json")
geo = D("geo/geo.json")

# effective dates for shared-code changes, from the TSB notes
R = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
eff = {}
for n in notes:
    for ln in n["text"].splitlines():
        m = re.search(r"(?<!\d)(901|991) (\d{2})(?!\d)", ln)
        ds = re.findall(r"(\d{1,2})\.([IVX]+)\.(\d{4})", ln)
        if m and ds:
            dd, mo, y = ds[0]
            eff[(n["issue"], m.group(1), m.group(2))] = f"{y}-{R[mo]:02d}-{int(dd):02d}"

type_of = {(r["mcc"], r["mnc"], r["country"]): (r["type"], r["type_tier"]) for r in reg}
A3 = {k: v["a3"] for k, v in iso.items()}

CH = []
for c in changes:
    t, tier = type_of.get((c["mcc"], c["mnc"], c["country"]), ("unclassified", None))
    CH.append({
        "i": c["issue"], "d": c["date"], "a": c["amendment"], "op": c["op"], "mcc": c["mcc"], "mnc": c["mnc"],
        "c": c["country"], "s": c["scope"], "n": c["network"], "note": c.get("note"),
        "prev": c.get("previous_holder") or c.get("previous_name"), "reissued": bool(c.get("previous_holder")),
        "undoc": c.get("name_differs_from_register"), "eff": eff.get((c["issue"], c["mcc"], c["mnc"])),
        "t": t, "tt": tier, "a3": A3.get(c["country"]),
    })

RG = [[r["mcc"], r["mnc"], r["country"], r["scope"], r["network"], r["status"], r["type"], r["type_tier"], r["type_basis"],
       [[h["event"], h["issue"], h["date"], h["network"]] for h in r["history"]], A3.get(r["country"])] for r in reg]

ISS = [{"i": x["issue"], "d": x["date"], "am": x["amendments"], "n": x["entries"]} for x in sorted(issues, key=lambda x: -x["issue"])]
NOTES = [{"i": n["issue"], "d": n["date"], "k": n["kind"], "codes": n["codes"], "t": n["text"].strip("\n")} for n in notes]

ahead = sorted([r for r in cmp["rows"] if r["bucket"] == "national_only"], key=lambda r: (r["nat_date"] or "0000"), reverse=True)
AHEAD = [{"mcc": r["mcc"], "mnc": r["mnc"], "c": r["country"], "a3": A3.get(r["country"]), "n": r["nat_holder"], "d": r["nat_date"],
          "reg": r["registry"], "t": type_of.get((r["mcc"], r["mnc"], r["country"]), (None,))[0]} for r in ahead]

# types for the ahead-of-ITU codes are not in the register; classify by the same rules
sys.path.insert(0, f"{root}/scripts")
import classify as K
for a in AHEAD:
    t, tier, why = K.classify({"mcc": a["mcc"], "mnc": a["mnc"], "network": a["n"] or ""}, None)
    a["t"], a["tt"] = t, tier

# first-sightings ledger
import os
LED = json.load(open(f"{root}/data/sightings.json")) if os.path.exists(f"{root}/data/sightings.json") else {}
for a in AHEAD:
    e = LED.get(f'{a["c"]}|{a["mcc"]} {a["mnc"]}')
    a["fs"] = e["first_seen"] if e else None
for e in LED.values():
    if e["status"] == "published":
        for c in CH:
            if c["i"] == e["itu_issue"] and c["mcc"] == e["mcc"] and c["mnc"] == e["mnc"] and c["c"] == e["country"]:
                c["sighted"] = {"first_seen": e["first_seen"], "nat_date": e["nat_date"], "gap": e["gap_days"], "registry": e["registry"]}

NAT = {
    "summary": cmp["summary"], "meta": cmp["meta"],
    "rows": [r for r in cmp["rows"] if r["bucket"] != "same"],
    "cbrs": cmp["cbrs"], "hk_trunk": len(cmp.get("hk_trunk", [])),
    "not_checked": [
        {"c": "Spain", "who": "CNMC", "why": "The numbering search sits behind a bot check, so it cannot be read automatically."},
        {"c": "Australia", "who": "ACMA", "why": "The register of other numbers refuses automated requests. Due a retry through a browser."},
        {"c": "France", "who": "Arcep", "why": "No consolidated MNC list found; assignments appear only as individual decisions."},
        {"c": "Sweden", "who": "PTS", "why": "No current list found; the plan documents that carried assignments have moved."},
        {"c": "Switzerland", "who": "OFCOM", "why": "Offers a search service only, with no downloadable list."},
        {"c": "Japan", "who": "MIC", "why": "No public MNC list found."},
        {"c": "India", "who": "DoT", "why": "No public MNC list found."},
    ],
    "flags": [{"mcc": "314", "mnc": "620", "text": "The ITU published Memphis Light, Gas and Water on 314 620 in No. 1316 (15 May 2025). The US administrator lists the utility only on 314 840 and has no entry for 314 620. Either the ITU entry is a transcription error or the code moved. Unresolved."}],
}

# forward schedule printed in No. 1348
SCHEDULE = [{"i": 1351, "pub": "2026-11-01", "cutoff": "2026-10-15"}, {"i": 1352, "pub": "2026-11-15", "cutoff": "2026-10-31"},
            {"i": 1353, "pub": "2026-12-01", "cutoff": "2026-11-13"}, {"i": 1354, "pub": "2026-12-15", "cutoff": "2026-11-30"},
            {"i": 1355, "pub": "2027-01-01", "cutoff": "2026-12-11"}]

latest = ISS[0]
stats = {
    "latest": latest["i"], "latest_date": latest["d"], "active": sum(1 for r in reg if r["status"] == "active"),
    "withdrawn": sum(1 for r in reg if r["status"] == "withdrawn"), "changes": len(CH), "ops": dict(Counter(c["op"] for c in CH)),
    "amendments": sum(len(x["am"]) for x in ISS), "issues": len(ISS), "built": datetime.date.today().isoformat(),
    "typed": sum(1 for r in reg if r["status"] == "active" and r["type"] != "unclassified"),
    "tiers": dict(Counter(r["type_tier"] or "none" for r in reg if r["status"] == "active")),
}

# researched cards: enforce the headline rule, then attach to the changes they cover
cards_doc = D("data/cards.json")
CARDS = {}
for card in cards_doc["cards"]:
    assert card["headline_tiers"] and "inferred" not in card["headline_tiers"], f"headline rests on an inferred claim: {card['id']}"
    for cl in card["claims"]:
        assert cl["t"] in cards_doc["tiers"], cl
        assert all(0 <= i < len(card["sources"]) for i in cl["src"]), (card["id"], cl)
    CARDS[card["id"]] = card
    for code in card["codes"]:
        mcc, mnc = code.split()
        hit = [c for c in CH if c["i"] == card["issue"] and c["mcc"] == mcc and c["mnc"] == mnc]
        assert hit, f"card {card['id']} names {code}, which has no change in No. {card['issue']}"
        for c in hit:
            c["card"] = card["id"]
            if card.get("type"):
                c["t"], c["tt"] = card["type"], card["type_tier"]
print("cards:", len(CARDS))

bundle = {"stats": stats, "cards": CARDS, "card_tiers": cards_doc["tiers"], "types": typed["types"], "changes": CH, "register": RG, "issues": ISS, "notes": NOTES,
          "ahead": AHEAD, "nat": NAT, "schedule": SCHEDULE,
          "geo": {"w": geo["width"], "h": geo["height"], "sphere": geo["sphere"], "land": geo["land"], "borders": geo["borders"], "pts": geo["points"]}}
payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = open(tpl, encoding="utf-8").read().replace("/*__DATA__*/null", payload)
open(out, "w", encoding="utf-8").write(html)
print(f"written {out}: {len(html)/1024:.0f} KB | ahead-of-ITU: {len(AHEAD)} | stats: {stats}")
