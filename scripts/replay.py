"""Replay MNC amendments onto the OB 1280 baseline to rebuild the current register.

Usage: python3 -I replay.py <baseline_json> <amend_pdf_json> <amend_docx_json> <out_dir>
Writes: register.json (current codes, with history), changes.json (ordered change log),
        conflicts.json (anything that did not apply cleanly).
"""
import json, re, sys, unicodedata
from collections import defaultdict

SCOPE_BY_MCC = {"901": "international", "902": "roio_sdo", "991": "trial"}
SCOPE_LABEL = {"international": "International (shared code)",
               "roio_sdo": "ROIO/SDO-specified (shared code)",
               "trial": "Trial of a proposed new international service (shared code)"}


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()


def main(bpath, ppath, dpath, outdir):
    base = json.load(open(bpath))
    pdf = json.load(open(ppath))
    dx = json.load(open(dpath))
    dx_name = {(e["issue"], e["op"], e["mcc"], e["mnc"]): e["name"] for e in dx["entries"]}

    countries = sorted({c["country"] for c in base["codes"] if c["scope"] == "geographic"})
    cset = set(countries)

    reg = {}  # key -> record
    def key(mcc, mnc, country):
        scope = SCOPE_BY_MCC.get(mcc, "geographic")
        return (mcc, mnc, SCOPE_LABEL[scope] if scope != "geographic" else country)

    for c in base["codes"]:
        k = key(c["mcc"], c["mnc"], c["country"])
        reg[k] = {"mcc": c["mcc"], "mnc": c["mnc"], "country": k[2], "scope": c["scope"],
                  "network": norm(c["network"]), "status": "active",
                  "history": [{"event": "baseline", "issue": 1280, "date": "2023-11-15", "network": norm(c["network"])}]}

    entries = sorted(pdf["entries"], key=lambda e: (e["issue"], e["amendment"]))
    changes, conflicts, unknown_countries = [], [], defaultdict(list)
    for e in entries:
        mcc, mnc, op = e["mcc"], e["mnc"], e["op"]
        scope = SCOPE_BY_MCC.get(mcc, "geographic")
        country = norm(e["country"])
        if scope == "geographic" and country not in cset:
            unknown_countries[country].append((e["issue"], mcc, mnc))
        k = key(mcc, mnc, country)
        name_pdf = norm(e["name"])
        name_dx = dx_name.get((e["issue"], op, mcc, mnc))
        name = norm(name_dx) if name_dx else name_pdf
        # strip a trailing parenthetical note the Word parse kept inline
        if e.get("note") and name.endswith(norm(e["note"])):
            name = name[: -len(norm(e["note"]))].strip()
        src = "word+pdf" if name_dx else "pdf"
        ch = {"issue": e["issue"], "date": e["date"], "amendment": e["amendment"], "op": op,
              "mcc": mcc, "mnc": mnc, "country": k[2], "scope": scope, "network": name,
              "note": e.get("note"), "name_source": src, "flags": e["flags"]}
        cur = reg.get(k)
        if op == "ADD":
            if cur and cur["status"] == "active":
                conflicts.append({**ch, "problem": "ADD for a code already active", "existing": cur["network"]})
                ch["applied"] = False
            else:
                if cur:  # re-assignment of a withdrawn code
                    ch["previous_holder"] = cur["network"]
                    cur.update({"network": name, "status": "active"})
                    cur["history"].append({"event": "reassigned", "issue": e["issue"], "date": e["date"], "network": name})
                else:
                    reg[k] = {"mcc": mcc, "mnc": mnc, "country": k[2], "scope": scope, "network": name,
                              "status": "active",
                              "history": [{"event": "assigned", "issue": e["issue"], "date": e["date"], "network": name}]}
                ch["applied"] = True
        elif op == "SUP":
            if not cur or cur["status"] != "active":
                conflicts.append({**ch, "problem": "SUP for a code not active"})
                ch["applied"] = False
            else:
                if norm(cur["network"]).lower() != name.lower():
                    ch["name_differs_from_register"] = cur["network"]
                cur["status"] = "withdrawn"
                cur["history"].append({"event": "withdrawn", "issue": e["issue"], "date": e["date"], "network": cur["network"]})
                ch["applied"] = True
        elif op == "LIR":
            if not cur:
                conflicts.append({**ch, "problem": "LIR for a code not in register"})
                # treat as an assignment so the register is complete, but flagged
                reg[k] = {"mcc": mcc, "mnc": mnc, "country": k[2], "scope": scope, "network": name,
                          "status": "active", "history": [{"event": "amended_unbased", "issue": e["issue"], "date": e["date"], "network": name}]}
                ch["applied"] = "as_add"
            else:
                ch["previous_name"] = cur["network"]
                if cur["status"] != "active":
                    conflicts.append({**ch, "problem": "LIR for a withdrawn code"})
                cur["history"].append({"event": "amended", "issue": e["issue"], "date": e["date"],
                                       "network": name, "previous": cur["network"]})
                cur["network"] = name
                ch["applied"] = True
        if e.get("note"):
            reg[k]["note"] = e["note"]
        changes.append(ch)

    json.dump(sorted(reg.values(), key=lambda r: (r["mcc"], r["mnc"].zfill(3), r["country"])),
              open(f"{outdir}/register.json", "w"), ensure_ascii=False, indent=1)
    json.dump(changes, open(f"{outdir}/changes.json", "w"), ensure_ascii=False, indent=1)
    json.dump({"conflicts": conflicts, "unknown_countries": unknown_countries},
              open(f"{outdir}/conflicts.json", "w"), ensure_ascii=False, indent=1)

    from collections import Counter
    st = Counter(r["status"] for r in reg.values())
    print("register records:", len(reg), dict(st))
    print("changes applied:", Counter(str(c["applied"]) for c in changes))
    print("conflicts:", len(conflicts))
    for c in conflicts:
        print("  ", c["issue"], c["op"], c["mcc"], c["mnc"], c["country"], "|", c["network"], "|", c["problem"], "|", c.get("existing", ""))
    print("amendment country names not in baseline:", dict(unknown_countries))
    print("re-assignments:", [(c["mcc"], c["mnc"], c["previous_holder"], "->", c["network"]) for c in changes if c.get("previous_holder")])
    print("SUP where register name differs:", sum(1 for c in changes if c.get("name_differs_from_register")))


if __name__ == "__main__":
    main(*sys.argv[1:5])
