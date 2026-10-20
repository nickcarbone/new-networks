"""Compare national registries with the rebuilt ITU register.

Usage: python3 -I compare.py <register_json> <registries_json> <out_json>
Buckets per code:
  same            in both, holder names agree
  holder_differs  in both, holder names disagree
  national_only   assigned nationally, not active in the ITU list (ITU gap)
  itu_only        active in the ITU list, not assigned nationally (stale ITU entry, or released)
"""
import json, re, sys, unicodedata
from difflib import SequenceMatcher
from collections import Counter, defaultdict

SUFFIX = r"\b(ltd|limited|inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|gmbh|ag|kg|b\.?v|n\.?v|oy|oyj|ab|plc|pty|s\.?a|s\.?a\.?u|sa|llp|lp|the|holdings?|group|operations?|uk|canada|mbh|se|ges|f|of|and|und|de|la|le|hk|hong kong|china|international|communications?|telecom(munications)?|networks?|wireless|mobile|services?|solutions?)\b"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^\w\s&]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(s):
    return re.sub(r"\s+", " ", re.sub(SUFFIX, " ", norm(s))).strip()


def initials(s):
    return "".join(w[0] for w in re.sub(r"[^\w\s]", " ", s or "").split() if w[0].isalpha()).lower()


PLACEHOLDER = re.compile(r"reserved for public safety|test imsi|^test$|government use", re.I)


def agree(a, b):
    if not a or not b:
        return False
    sa, sb = (a or "").strip(), (b or "").strip()
    for x, y in ((sa, sb), (sb, sa)):
        if 1 < len(x) <= 5 and x.replace(".", "").isupper() and x.replace(".", "").lower() == initials(y):
            return True
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    ca, cb = core(a), core(b)
    if ca and cb and (ca == cb or ca in cb or cb in ca):
        return True
    ta = {w for w in ca.split() if len(w) >= 4}
    tb = {w for w in cb.split() if len(w) >= 4}
    if ta & tb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.72


reg = json.load(open(sys.argv[1]))
nat = json.load(open(sys.argv[2]))
COUNTRY_MCC = {"United States": {"310", "311", "312", "313", "314", "315", "316"}, "Canada": {"302"},
               "United Kingdom": {"234", "235"}, "Germany": {"262"}, "Hong Kong, China": {"454"},
               "Finland": {"244"}, "Netherlands": {"204"}}
REG_OF = {"us_imsi": "United States", "ca_cnac": "Canada", "uk_ofcom": "United Kingdom", "de_bnetza": "Germany",
          "hk_ofca": "Hong Kong, China", "fi_traficom": "Finland", "nl_acm": "Netherlands"}

itu = defaultdict(dict)
for r in reg:
    if r["scope"] == "geographic":
        itu[r["country"]][(r["mcc"], r["mnc"])] = r

out, summary = [], {}
for regid, country in REG_OF.items():
    nrecs = {(x["mcc"], x["mnc"]): x for x in nat["records"] if x["registry"] == regid}
    mccs = COUNTRY_MCC[country]
    icodes = {k: v for k, v in itu[country].items() if k[0] in mccs}
    # ITU entries for these MCCs filed under another country label (e.g. Crown dependencies under UK MCC)
    others = {(r["mcc"], r["mnc"]): r for r in reg if r["scope"] == "geographic" and r["mcc"] in mccs and r["country"] != country}
    keys = set(icodes) | {k for k, v in nrecs.items() if v["status"] in ("assigned",)}
    cnt = Counter()
    for k in sorted(keys, key=lambda k: (k[0], k[1].zfill(3))):
        i = icodes.get(k)
        n = nrecs.get(k)
        i_active = bool(i and i["status"] == "active")
        n_assigned = bool(n and n["status"] == "assigned")
        placeholder = bool(i and PLACEHOLDER.search(i["network"] or "")) and bool(n and n["status"] in ("reserved", "test"))
        if i_active and placeholder:
            b = "same"
        elif i_active and n_assigned:
            b = "same" if agree(i["network"], n["holder"]) else "holder_differs"
        elif n_assigned and not i_active:
            b = "national_only"
        elif i_active and not n_assigned:
            b = "itu_only"
        else:
            continue  # withdrawn in ITU and not assigned nationally: consistent
        if b == "national_only" and k in others:
            b = "filed_elsewhere"
        cnt[b] += 1
        out.append({
            "registry": regid, "country": country, "mcc": k[0], "mnc": k[1], "bucket": b,
            "itu_holder": i["network"] if i else None, "itu_status": i["status"] if i else None,
            "itu_last": i["history"][-1] if i else None, "itu_first": i["history"][0] if i else None,
            "nat_holder": n["holder"] if n else None, "nat_status": n["status"] if n else None,
            "nat_date": n["date"] if n else None, "nat_remark": n["remark"] if n else None,
            "elsewhere": others[k]["country"] if k in others else None,
        })
    summary[regid] = {"country": country, "national_assigned": sum(1 for v in nrecs.values() if v["status"] == "assigned"),
                      "itu_active": sum(1 for v in icodes.values() if v["status"] == "active"), **cnt}

json.dump({"summary": summary, "rows": out, "meta": nat["meta"], "cbrs": nat["cbrs"], "hk_trunk": nat.get("hk_trunk", [])}, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
for k, v in summary.items():
    print(f"{k:12s}", v)
