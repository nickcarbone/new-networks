"""Extract TSB notes relevant to MNCs from the general section of each OB.

Captures: 'Identification codes for International Mobile Networks' (MCC 901),
'Identification codes for international non-commercial trials' (MCC 991),
and 'Extra-territorial use of Mobile Country Code (MCC) and Mobile Network Code (MNC)'.
Usage: python3 -I extract_notes.py <pdftext_dir> <out_json>
"""
import json, os, re, sys

HEADS = {
    "international_mobile": re.compile(r"^\s*Identification codes for International Mobile Networks\s*$"),
    "trial": re.compile(r"^\s*Identification codes for international non-commercial trials\s*$"),
    "extra_territorial": re.compile(r"^\s*Extra-territorial use of Mobile Country Code \(MCC\)\s*$"),
}
END = re.compile(
    r"^\s*(Identification codes for international|Extra-territorial use of Mobile|Telephone Service|Service Restrictions|"
    r"Call-Back|List of Ship Stations|Approval of ITU-T|AMENDMENTS TO SERVICE|Changes to Service|Mobile Network Codes \(MNC\) for|"
    r"List of ITU Carrier|List of Issuer|List of International Signalling|National Numbering Plan|Lists annexed)"
)
PAGE = re.compile(r"^\s*(No\. \d{4} – \d+\s+ITU Operational Bulletin|ITU Operational Bulletin\s+No\. \d{4} – \d+)\s*$")
ISSUE_DATE = re.compile(r"No\.\s*(\d{4})\s+(\d{1,2})\.([IVX]+)\.(\d{4})")
ISSUE_DATE_LONG = re.compile(r"No\.\s*(\d{4})\s*\((\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})\)")
MONTHS = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}


def main(d, out):
    notes = []
    for fn in sorted(os.listdir(d)):
        issue = int(fn[:-4])
        lines = open(os.path.join(d, fn), encoding="utf-8", errors="replace").read().splitlines()
        date = None
        for m in ISSUE_DATE.finditer("\n".join(lines[:60])):
            if m.group(1) == str(issue):
                date = f"{m.group(4)}-{ROMAN[m.group(3)]:02d}-{int(m.group(2)):02d}"; break
        if not date:
            for m in ISSUE_DATE_LONG.finditer("\n".join(lines[:60])):
                if m.group(1) == str(issue):
                    date = f"{m.group(4)}-{MONTHS[m.group(3)]:02d}-{int(m.group(2)):02d}"; break
        for i, ln in enumerate(lines):
            for kind, rx in HEADS.items():
                if rx.match(ln) and "…" not in ln and "...." not in ln:
                    body = []
                    for ln2 in lines[i + 1:i + 120]:
                        if END.match(ln2) and body:
                            break
                        if PAGE.match(ln2):
                            continue
                        body.append(ln2.rstrip())
                    while body and not body[-1].strip():
                        body.pop()
                    text = "\n".join(body)
                    codes = sorted(set(re.findall(r"(?<!\d)(9\d{2}|\d{3})\s(\d{2,3})(?!\d)", text)))
                    notes.append({"issue": issue, "date": date, "kind": kind, "text": text,
                                  "codes": [f"{a} {b}" for a, b in codes if a in ("901", "902", "991") or kind == "extra_territorial"]})
    json.dump(notes, open(out, "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("notes:", len(notes), dict(Counter(n["kind"] for n in notes)))


if __name__ == "__main__":
    main(*sys.argv[1:3])
