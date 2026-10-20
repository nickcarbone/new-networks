"""Normalise national MNC registries into one record format.

Record: {registry, country, mcc, mnc, holder, status, date, remark}
status: 'assigned' | 'returned' | 'reserved' | 'free' | 'test'
Usage: python3 -I parse_registries.py <raw_dir> <out_json>
"""
import csv, html, json, re, sys
from collections import Counter

raw, outp = sys.argv[1:3]


def cells(t):
    for r in re.findall(r"<tr.*?</tr>", t, flags=re.S | re.I):
        yield [html.unescape(re.sub(r"<.*?>", "", c)).strip() for c in re.findall(r"<t[dh].*?</t[dh]>", r, flags=re.S | re.I)]


def d_mdy(s):  # 10/20/25 or 10/20/2025
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if not m:
        return None
    y = int(m.group(3)); y = y + 2000 if y < 100 else y
    return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"


def d_dmy(s, sep):
    m = re.search(r"(\d{1,2})" + re.escape(sep) + r"(\d{1,2})" + re.escape(sep) + r"(\d{4})", s or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


recs = []
meta = {}

# --- United States: IMSI Administrator HNI list
rows = json.load(open(f"{raw}/us_hni_rows.json"))
for code, ent in rows:
    mcc, mnc = code.split("-")
    e = ent.strip()
    if re.match(r"(returned|reclaimed)", e, re.I):
        st, holder = "returned", re.sub(r"(?i)^(returned|reclaimed)( on)?\s*[\d/]*\s*", "", e).strip(" ()-") or None
        if holder and re.fullmatch(r"\d{3}-\d{3}", holder):
            holder = None
    elif re.search(r"reserved for public safety", e, re.I):
        st, holder = "reserved", None
    elif re.search(r"test imsi", e, re.I):
        st, holder = "test", None
    elif re.search(r"available for assignment", e, re.I):
        st, holder = "free", None
    else:
        st, holder = "assigned", e
    recs.append({"registry": "us_imsi", "country": "United States", "mcc": mcc, "mnc": mnc, "holder": holder,
                 "status": st, "date": d_mdy(e) if st == "returned" else None, "remark": e if st != "assigned" else None})
meta["us_imsi"] = {"name": "IMSI Administrator (iconectiv, for the ATIS IMSI Oversight Council)", "country": "United States",
                   "url": "https://imsiadmin.com/assignments/hni/", "method": "direct download", "as_of": "2026-10-19 (retrieved)"}

# --- United States: CBRS shared HNI 315-010 sub-assignments (IBN)
t = open(f"{raw}/us_cbrs.html", encoding="utf-8", errors="replace").read()
cbrs = []
for c in cells(t):
    if len(c) >= 3 and re.match(r"315-010", c[0]) and re.fullmatch(r"\d{4}", c[1]):
        cbrs.append({"hni": c[0], "ibn": c[1], "holder": c[2]})
meta["us_cbrs"] = {"name": "IMSI Administrator, CBRS shared HNI 315-010", "country": "United States",
                   "url": "https://imsiadmin.com/assignments/cbrs/", "method": "direct download", "as_of": "2026-10-19 (retrieved)"}

# --- Canada: CNAC IMSI/MNC status
t = open(f"{raw}/ca_cnac.html", encoding="latin-1").read()
for c in cells(t):
    if len(c) >= 6 and c[0] == "302" and re.fullmatch(r"\d{3}", c[1]):
        s = c[2].lower()
        st = "assigned" if "in service" in s or "assigned" in s else "returned" if "recovered" in s or "aging" in s else "reserved" if "reserved" in s else "free" if "available" in s else s
        recs.append({"registry": "ca_cnac", "country": "Canada", "mcc": c[0], "mnc": c[1], "holder": c[3] or None,
                     "status": st, "date": c[4] or None, "remark": " ".join(x for x in (c[2], c[5]) if x)})
meta["ca_cnac"] = {"name": "Canadian Numbering Administrator (CNAC)", "country": "Canada",
                   "url": "https://cnac.ca/data/MNC_Codes.htm", "method": "direct download", "as_of": "2026-10-19 (retrieved)"}

# --- United Kingdom: Ofcom mnc.csv (read through the web fetcher; Cloudflare blocks direct download)
for r in csv.DictReader(open(f"{raw}/uk_mnc_webfetch.csv", encoding="utf-8")):
    mcc, mnc = r["Number Block"].split()
    st = "assigned" if r["Block Status"] == "Allocated" else "free"
    recs.append({"registry": "uk_ofcom", "country": "United Kingdom", "mcc": mcc, "mnc": mnc, "holder": r["CP Name"] or None,
                 "status": st, "date": d_dmy(r["Allocation Date"], "/"), "remark": None})
meta["uk_ofcom"] = {"name": "Ofcom numbering data, Mobile Network Codes", "country": "United Kingdom",
                    "url": "https://www.ofcom.org.uk/phones-telecoms-and-internet/information-for-industry/numbering/numbering-data",
                    "method": "read through web fetcher (direct download blocked by a bot check); not byte-exact",
                    "as_of": "2026-10-14 (Ofcom weekly update)"}

# --- Germany: BNetzA IMSI allocated blocks (PDF)
import subprocess
txt = subprocess.run(["pdftotext", "-layout", f"{raw}/bnetza_imsi.pdf", "-"], capture_output=True, text=True).stdout
as_of = re.search(r"Stand:\s*(\d{2}\.\d{2}\.\d{4})", txt)
lines = txt.splitlines()
de = []
for i, ln in enumerate(lines):
    m = re.match(r"^\s*262\s+(\d{2,3})\s*(.*)$", ln)
    if m:
        name = m.group(2).strip()
        if not name:  # wrapped holder: lines above and below
            above = lines[i - 1].strip() if i > 0 and not re.match(r"^\s*262\s", lines[i - 1]) else ""
            below = lines[i + 1].strip() if i + 1 < len(lines) and not re.match(r"^\s*262\s", lines[i + 1]) else ""
            name = " ".join(x for x in (above, below) if x)
        de.append((m.group(1), name))
for mnc, name in de:
    recs.append({"registry": "de_bnetza", "country": "Germany", "mcc": "262", "mnc": mnc, "holder": name,
                 "status": "assigned", "date": None, "remark": None})
meta["de_bnetza"] = {"name": "Bundesnetzagentur, IMSI allocated blocks", "country": "Germany",
                     "url": "https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Nummerierung/IMSI/DL/imsi_zugbloecke.html",
                     "method": "direct download (PDF)", "as_of": d_dmy(as_of.group(1), ".") if as_of else None}

# --- Hong Kong: OFCA
hk_trunk = []
for r in csv.DictReader(open(f"{raw}/hk_mnc.csv", encoding="utf-8-sig")):
    holder = r["MNC_ASSIGNEE"].strip()
    ntype = r["MNC_NETWORK_TYPE"].strip()
    st = "free" if "Spare" in holder else "on_hold" if "On Hold" in holder else "reserved" if re.search(r"reserved", holder, re.I) else "assigned"
    raw_code = r["MNC"].strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw_code)
    codes = [str(x).zfill(len(m.group(1))) for x in range(int(m.group(1)), int(m.group(2)) + 1)] if m else [raw_code]
    rec_base = {"registry": "hk_ofca", "country": "Hong Kong, China", "mcc": "454",
                "holder": None if st not in ("assigned",) else holder, "status": st, "date": None,
                "remark": " · ".join(x for x in (ntype, r["MNC_REMARK"].strip()) if x) or None}
    if "Trunk Radio" in ntype:
        # OFCA lists trunk radio codes in the same table; they are not in the ITU E.212 list
        hk_trunk += [{**rec_base, "mnc": c, "holder": holder, "raw_code": raw_code} for c in codes]
        continue
    for c in codes:
        recs.append({**rec_base, "mnc": c, "raw_code": raw_code})
meta["hk_ofca"] = {"name": "OFCA, Assignment of Mobile Network Code (DATA.GOV.HK)", "country": "Hong Kong, China",
                   "url": "https://data.gov.hk/en-data/dataset/hk-ofca-ofca-ofca-dataset-17", "method": "direct download", "as_of": "2026-10-19 (retrieved)"}

# --- Finland: Traficom e-service
for r in csv.DictReader(open(f"{raw}/fi_mnc.csv", encoding="utf-8")):
    recs.append({"registry": "fi_traficom", "country": "Finland", "mcc": "244", "mnc": r["mnc"], "holder": r["company"],
                 "status": "assigned", "date": d_dmy(r["decision_date"], "."), "remark": None})
meta["fi_traficom"] = {"name": "Traficom, approved mobile network codes", "country": "Finland",
                       "url": "https://eservices.traficom.fi/LicensesServices/Forms/NureMnctunnukset.aspx?langid=en",
                       "method": "direct download (all pages)", "as_of": "2026-10-19 (retrieved)"}

# --- Netherlands: ACM number register
for r in csv.DictReader(open(f"{raw}/nl/nummers.csv", encoding="utf-8", errors="replace"), delimiter=";"):
    if "mobiele netwerkcode" not in r["twn_bestemming"].lower():
        continue
    a, b = r["twn_nummervan"].strip(), r["twn_nummertm"].strip()
    codes = [a] if a == b else [str(x).zfill(len(a)) for x in range(int(a), int(b) + 1)]
    for mnc in codes:
        recs.append({"registry": "nl_acm", "country": "Netherlands", "mcc": "204", "mnc": mnc,
                     "holder": r["twn_relatienaam"].strip(), "status": "assigned" if r["twn_nummerstatus"] == "Toegekend" else r["twn_nummerstatus"].lower(),
                     "date": d_dmy(r["twn_datumbeschikking"], "-"), "remark": r["twn_bestemming"] + (f"; ends {r['twn_datumeind']}" if r["twn_datumeind"] else "")})
meta["nl_acm"] = {"name": "ACM, register of assigned numbers", "country": "Netherlands",
                  "url": "https://www.acm.nl/nl/onderwerpen/telecommunicatie/telefoonnummers/nummers-doorzoeken",
                  "method": "direct download (CSV)", "as_of": "2026-10-19 (retrieved)"}

json.dump({"records": recs, "cbrs": cbrs, "hk_trunk": hk_trunk, "meta": meta}, open(outp, "w"), ensure_ascii=False, indent=1)
c = Counter((r["registry"], r["status"]) for r in recs)
for reg in meta:
    print(f"{reg:12s}", {k[1]: v for k, v in c.items() if k[0] == reg})
print("cbrs sub-assignments:", len(cbrs), "| HK trunk radio rows set aside:", len(hk_trunk))
dups = Counter((r["registry"], r["mcc"], r["mnc"]) for r in recs)
print("duplicate codes within a registry:", [k for k, v in dups.items() if v > 1][:10])
print("German holders reassembled:", [(m, n) for m, n in de if len(n) > 60])
