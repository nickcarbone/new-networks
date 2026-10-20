"""Parse MNC amendments (annex to OB No. 1280) from ITU OB PDF text (pdftotext -layout).

The PDF text is the source of truth for which entries exist. Names that wrap
are reassembled using the layout geometry: names are vertically centred on
their code, so wrapped lines can sit above and/or below the code line.
Entries whose names were reassembled are flagged for checking.

Usage: python3 -I parse_amendments.py <pdftext_dir> <out_json>
"""
import json, os, re, sys

START = re.compile(r"Annex to ITU Operational Bulletin No\.\s*1280")
AMEND = re.compile(r"Amendment\s+No\.?\s*(\d+)")
STOP = re.compile(
    r"Annex to ITU Operational Bulletin No\.\s*(?!1280)\d+"
    r"|^\s*List of (ITU Carrier Codes|International Signalling Point Codes|Issuer Identifier Numbers|Ship Stations)"
    r"|^\s*(Service Restrictions|SERVICE RESTRICTIONS|National Numbering Plan|Telephone Service|AMENDMENTS TO SERVICE)"
    r"|^\s*See page \d+ of the present Operational Bulletin"
)
PAGE_HDR = re.compile(r"^\s*(No\. \d{4} – \d+\s+ITU Operational Bulletin|ITU Operational Bulletin\s+No\. \d{4} – \d+)\s*$")
OP_LINE = re.compile(r"^(?P<ind>\s*)(?P<country>\S.*?)\s+(?P<op>ADD|SUP|LIR)\s*\*?\s*$")
OP_MID = re.compile(r"^(?P<ind>\s*)(?P<country>\S.*?)\s+(?P<op>ADD|SUP|LIR)\s*\*?\s{3,}(?P<rest>\S.*)$")
CODE_LINE = re.compile(r"^(?P<ind>\s*)(?P<mcc>\d{3}) (?P<mnc>\d{2,3})(?!\d)\s*\*?(?P<post>.*)$")
FOOT = re.compile(r"^\s*(_{4,}|\*|MCC:|MNC:|MSIN\b|MSIN:|As defined in Annex E|the situation where|country, Country B)")
HEADERISH = re.compile(
    r"^\s*(Country\s*/\s*Geographical|Country/Geographical|Country or\b|Country\s*$|or Geographical Area|MCC\s*\+\s*MNC|"
    r"Name of assignee|Operator/Network|Mobile Network Codes \(MNC\)|for public networks and subscriptions|"
    r"\(According to Recommendation|\(Position on|- Position on|Position on 15 November 2023|Networks\s*$|"
    r"Applicant|\(?Annex to ITU|\(?Amendment No)"
)
EXTRA_HDR = re.compile(r"Extra-territorial use", re.I)
ISSUE_DATE = re.compile(r"No\.\s*(\d{4})\s+(\d{1,2})\.([IVX]+)\.(\d{4})")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
NOTE = re.compile(r"^\((temporary|valid|until|assignment)", re.I)


MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}
ISSUE_DATE_LONG = re.compile(r"No\.\s*(\d{4})\s*\((\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})\)")


def issue_date(text, issue):
    for m in ISSUE_DATE.finditer(text[:4000]):
        if m.group(1) == str(issue):
            return f"{m.group(4)}-{ROMAN[m.group(3)]:02d}-{int(m.group(2)):02d}"
    # header style introduced with No. 1350: 'No. 1350 (15 October 2026)'
    for m in ISSUE_DATE_LONG.finditer(text[:4000]):
        if m.group(1) == str(issue):
            return f"{m.group(4)}-{MONTHS[m.group(3)]:02d}-{int(m.group(2)):02d}"
    return None


def tokenise(lines):
    """Turn a section's lines into tokens: H (heading), C (code), T (text), X (extra-territorial)."""
    toks, mode = [], "mnc"
    for ln in lines:
        if not ln.strip() or PAGE_HDR.match(ln):
            continue
        if EXTRA_HDR.search(ln):
            mode = "extra"; continue
        if FOOT.match(ln):
            mode = "foot" if mode != "extra" else "extra_foot"; continue
        if HEADERISH.match(ln):
            continue
        if mode in ("foot", "extra_foot"):
            # footnote text can wrap; ignore until something structural appears
            if OP_LINE.match(ln) or CODE_LINE.match(ln):
                mode = "mnc" if mode == "foot" else "extra"
            else:
                continue
        if mode == "extra":
            toks.append(("X", ln.strip(), None)); continue
        mc, mo = CODE_LINE.match(ln), OP_LINE.match(ln)
        mid = None if (mc or mo) else OP_MID.match(ln)
        if mid and len(mid.group("ind")) < 12:
            # heading and content on one line: 'shared code LIR*      Name' or '... ADD*   991 04'
            toks.append(("H", (mid.group("country").strip(), mid.group("op")), len(mid.group("ind"))))
            rest_col = mid.start("rest")
            rest = mid.group("rest")
            mc2 = CODE_LINE.match(rest)
            if mc2:
                toks.append(("C", (mc2.group("mcc"), mc2.group("mnc"), mc2.group("post").strip()), rest_col))
            else:
                toks.append(("T", rest.strip(), rest_col))
            continue
        if mc:
            toks.append(("C", (mc.group("mcc"), mc.group("mnc"), mc.group("post").strip()), len(mc.group("ind"))))
        elif mo and len(mo.group("ind")) < 12:
            toks.append(("H", (mo.group("country").strip(), mo.group("op")), len(mo.group("ind"))))
        else:
            ind = len(ln) - len(ln.lstrip())
            toks.append(("T", ln.strip(), ind))
    # merge multi-line headings: low-indent text lines before a heading join it;
    # indented text lines found among them are name lines for the next code, so
    # they move after the heading.
    out = []
    for t in toks:
        if t[0] == "H":
            run = []
            while out and out[-1][0] == "T":
                run.insert(0, out.pop())
            first_low = next((k for k, p in enumerate(run) if p[2] < 12), None)
            if first_low is None:
                out.extend(run); prefix, held = [], []
            else:
                out.extend(run[:first_low])  # continuation of the previous entry
                prefix = [p for p in run[first_low:] if p[2] < 12]
                held = [p for p in run[first_low:] if p[2] >= 12]
            name = " ".join([p[1] for p in prefix] + [t[1][0]])
            out.append(("H", (name, t[1][1]), t[2]))
            out.extend(held)
        else:
            out.append(t)
    return out


def assemble(toks):
    """Attach text runs to code anchors using the centring rule."""
    entries, extra = [], []
    anchors = [i for i, t in enumerate(toks) if t[0] in "HC"]
    # build entries for code tokens
    ent_at = {}
    country = op = None
    for i, t in enumerate(toks):
        if t[0] == "H":
            country, op = t[1]
        elif t[0] == "C":
            mcc, mnc, post = t[1]
            ent_at[i] = {"country": country, "op": op, "mcc": mcc, "mnc": mnc,
                         "above": [], "line": post, "below": [], "note": None, "flags": []}
            if not country:
                ent_at[i]["flags"].append("no_heading")
            if not post:
                ent_at[i]["flags"].append("bare_code")
        elif t[0] == "X":
            extra.append(t[1])

    def run_after(i):
        r, j = [], i + 1
        while j < len(toks) and toks[j][0] == "T":
            r.append(j); j += 1
        return r

    # runs of text between anchors
    i = 0
    while i < len(toks):
        if toks[i][0] != "T":
            i += 1; continue
        j = i
        while j < len(toks) and toks[j][0] == "T":
            j += 1
        run = list(range(i, j))
        prev = i - 1 if i > 0 else None
        nxt = j if j < len(toks) else None
        prev_c = prev is not None and toks[prev][0] == "C"
        next_c = nxt is not None and toks[nxt][0] == "C"
        if not prev_c and next_c:
            ent_at[nxt]["above"] += [toks[k][1] for k in run]
        elif prev_c and not next_c:
            ent_at[prev]["below"] += [toks[k][1] for k in run]
        elif prev_c and next_c:
            nb = ent_at[nxt]
            if not nb["line"]:
                below_next = len(run_after(nxt))
                m = min(len(run), max(below_next, 1))
                ent_at[prev]["below"] += [toks[k][1] for k in run[:len(run) - m]]
                nb["above"] += [toks[k][1] for k in run[len(run) - m:]]
                if len(run) - m:
                    ent_at[prev]["flags"].append("split_run")
                    nb["flags"].append("split_run")
            else:
                ent_at[prev]["below"] += [toks[k][1] for k in run]
        else:
            for k in run:
                entries.append({"orphan_text": toks[k][1]})
        i = j

    for i in sorted(ent_at):
        e = ent_at[i]
        parts = e["above"] + ([e["line"]] if e["line"] else []) + e["below"]
        notes = [p for p in parts if NOTE.match(p)]
        parts = [p for p in parts if not NOTE.match(p)]
        e["name"] = re.sub(r"\s+", " ", " ".join(parts)).strip()
        e["note"] = " ".join(notes) or None
        if e["above"] or e["below"]:
            e["flags"].append("multiline")
        e["raw"] = parts + notes
        for k in ("above", "line", "below"):
            del e[k]
        entries.append(e)
    return entries, extra


def parse_issue(path, issue):
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = text.splitlines()
    date = issue_date(text, issue)
    sections = []
    i = 0
    while i < len(lines):
        if START.search(lines[i]):
            amend = None
            for j in range(i, min(i + 4, len(lines))):
                m = AMEND.search(lines[j])
                if m:
                    amend = int(m.group(1)); i = j; break
            if amend is None:
                i += 1; continue
            body = []
            i += 1
            while i < len(lines) and not STOP.search(lines[i]) and not START.search(lines[i]):
                body.append(lines[i]); i += 1
            sections.append((amend, body))
        else:
            i += 1
    out, extra, orphans = [], [], []
    for amend, body in sections:
        ents, ex = assemble(tokenise(body))
        for e in ents:
            if "orphan_text" in e:
                orphans.append({"issue": issue, "amendment": amend, "text": e["orphan_text"]})
                continue
            e.update({"issue": issue, "date": date, "amendment": amend})
            out.append(e)
        extra += [{"issue": issue, "date": date, "amendment": amend, "line": l} for l in ex]
    return date, [a for a, _ in sections], out, extra, orphans


def main(d, out):
    allent, allextra, allorph, issues = [], [], [], []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        issue = int(fn[:-4])
        date, amends, e, x, o = parse_issue(os.path.join(d, fn), issue)
        issues.append({"issue": issue, "date": date, "amendments": amends, "entries": len(e)})
        allent += e; allextra += x; allorph += o
    json.dump({"issues": issues, "entries": allent, "extra_territorial_lines": allextra,
               "orphans": allorph}, open(out, "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    got = sorted(a for it in issues for a in it["amendments"])
    print("issues:", len(issues), "| undated:", [it["issue"] for it in issues if not it["date"]])
    print("amendments:", len(got), "| missing:", sorted(set(range(1, max(got) + 1)) - set(got)),
          "| duplicated:", sorted({a for a in got if got.count(a) > 1}))
    print("entries:", len(allent), dict(Counter(e["op"] for e in allent)))
    print("flags:", dict(Counter(f for e in allent for f in set(e["flags"]))))
    print("orphan text lines:", len(allorph))
    for o in allorph[:30]:
        print("  ", o)


if __name__ == "__main__":
    main(*sys.argv[1:3])
