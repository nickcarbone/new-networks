"""Parse MNC amendments from OB Word files, including text in frames/textboxes.

Walks every paragraph (outside tables) and table row in document order using
the raw XML, so content python-docx's body iterator skips is still reached.
Usage: python3 -I parse_docx_amend.py <docx_dir> <out_json>
"""
import json, os, re, sys, zipfile
from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
START = re.compile(r"Annex to ITU Operational Bulletin No\.\s*1280")
AMEND = re.compile(r"Amendment\s+No\.?\s*(\d+)")
STOP = re.compile(r"Annex to ITU Operational Bulletin No\.\s*(?!1280)\d+|National Numbering Plan|^List of (ITU Carrier|International Signalling|Issuer Identifier)")
OP = re.compile(r"^(?P<country>.*?)\s*\b(?P<op>ADD|SUP|LIR)\s*\*?$")
CODE = re.compile(r"^(?P<mcc>\d{3})\s?(?P<mnc>\d{2,3})\s*\*?$")
EXTRA = re.compile(r"Extra-territorial use", re.I)


def text_of(el):
    return re.sub(r"\s+", " ", "".join(t.text or "" for t in el.iter(W + "t")).replace("\xa0", " ")).strip()


def walk(root):
    """Yield ('P', text) and ('R', [cell texts]) in document order."""
    for el in root.iter(W + "p", W + "tr"):
        if el.tag == W + "tr":
            cells = [text_of(tc) for tc in el.iter(W + "tc")]
            # dedupe merged-cell repeats next to each other
            out = []
            for c in cells:
                if not out or out[-1] != c:
                    out.append(c)
            yield "R", out
        else:
            anc = el.getparent()
            in_table = False
            while anc is not None:
                if anc.tag == W + "tbl":
                    in_table = True; break
                anc = anc.getparent()
            if not in_table:
                yield "P", text_of(el)


def parse(path, issue):
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    entries, extra, amends = [], [], []
    on, amend, country, op, mode, pending_country = False, None, None, None, "mnc", ""
    for kind, v in walk(root):
        if kind == "P":
            if START.search(v):
                on, amend, country, op, mode = True, None, None, None, "mnc"
                continue
            if not on:
                continue
            m = AMEND.search(v)
            if m and amend is None:
                amend = int(m.group(1)); amends.append(amend); continue
            if STOP.search(v):
                on = False; continue
            if EXTRA.search(v):
                mode = "extra"
            continue
        if not on or amend is None:
            continue
        cells = [c for c in v if c]
        if not cells:
            continue
        if mode == "extra":
            extra.append({"issue": issue, "amendment": amend, "cells": cells})
            continue
        # header-like rows
        if any(re.match(r"^(Country|MCC\s*\+?\s*MNC|Name of|Operator/Network)", c) for c in cells) and not any(CODE.match(c) for c in cells):
            continue
        code_idx = next((i for i, c in enumerate(cells) if CODE.match(c)), None)
        for c in cells:
            mo = OP.match(c)
            if mo and (code_idx is None or cells.index(c) < code_idx):
                country, op = (pending_country + " " + mo.group("country")).strip(), mo.group("op")
                pending_country = ""
        if code_idx is None:
            if not any(OP.match(c) for c in cells):
                # a country heading split over two rows, or a stray note
                if entries and entries[-1]["amendment"] == amend and len(cells) == 1 and cells[0].startswith("("):
                    entries[-1]["note"] = cells[0]
                else:
                    pending_country = (pending_country + " " + " ".join(cells)).strip()
            continue
        mc = CODE.match(cells[code_idx])
        name_cells = cells[code_idx + 1:]
        note = None
        if len(name_cells) > 1 and name_cells[-1].startswith("("):
            note = name_cells.pop()
        entries.append({"issue": issue, "amendment": amend, "country": country, "op": op,
                        "mcc": mc.group("mcc"), "mnc": mc.group("mnc"),
                        "name": " ".join(name_cells).strip(), "note": note})
    return amends, entries, extra


def main(d, out):
    # incremental: keep issues already parsed in <out>, replace any re-parsed now
    import os.path
    prev = json.load(open(out)) if os.path.exists(out) else {"issues": {}, "entries": [], "extra": []}
    allent, allextra, issues = [], [], {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".docx"):
            continue
        issue = int(fn.split(".")[1].split("-")[0])
        a, e, x = parse(os.path.join(d, fn), issue)
        issues[issue] = a
        allent += e; allextra += x
    redone = set(issues)
    for k, v in prev["issues"].items():
        if int(k) not in redone:
            issues[int(k)] = v
    allent += [e for e in prev["entries"] if e["issue"] not in redone]
    allextra += [e for e in prev["extra"] if e["issue"] not in redone]
    issues = {k: issues[k] for k in sorted(issues)}
    json.dump({"issues": issues, "entries": allent, "extra": allextra}, open(out, "w"), ensure_ascii=False, indent=1)
    got = sorted(a for v in issues.values() for a in v)
    from collections import Counter
    print("docx issues:", len(issues), "| amendments:", len(got), "| missing:", sorted(set(range(1, 65)) - set(got)))
    print("entries:", len(allent), dict(Counter(e["op"] for e in allent)))
    print("entries lacking country/op:", [ (e["issue"], e["mcc"], e["mnc"]) for e in allent if not e["op"] or not e["country"]][:10])
    print("entries with empty name:", [(e["issue"], e["mcc"], e["mnc"]) for e in allent if not e["name"]][:10])


if __name__ == "__main__":
    main(*sys.argv[1:3])
