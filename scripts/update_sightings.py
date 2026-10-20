"""Keep the ledger of codes seen in a national registry before the ITU published them.

data/sightings.json, keyed "<country>|<mcc> <mnc>":
  first_seen   date New Networks first saw it in the national registry (run date)
  nat_date     assignment date the registry gives, if any
  holder, registry
  itu_issue, itu_date, gap_days   filled once the ITU publishes the code
  status       'ahead' | 'published' | 'dropped' (left the national list before the ITU showed it)

Usage: python3 -I update_sightings.py <repo_root> [run_date YYYY-MM-DD]
"""
import datetime, json, os, sys

root = sys.argv[1]
today = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
path = f"{root}/data/sightings.json"
led = json.load(open(path)) if os.path.exists(path) else {}
cmp = json.load(open(f"{root}/reg/compare.json"))
reg = json.load(open(f"{root}/data/register.json"))
itu = {(r["country"], r["mcc"], r["mnc"]): r for r in reg}

now_ahead = set()
for r in cmp["rows"]:
    if r["bucket"] != "national_only":
        continue
    k = f'{r["country"]}|{r["mcc"]} {r["mnc"]}'
    now_ahead.add(k)
    e = led.get(k)
    if not e or e["status"] != "ahead":
        led[k] = {"country": r["country"], "mcc": r["mcc"], "mnc": r["mnc"], "first_seen": today,
                  "nat_date": r["nat_date"], "holder": r["nat_holder"], "registry": r["registry"], "status": "ahead"}
    else:
        e["holder"], e["nat_date"] = r["nat_holder"], r["nat_date"]

changed = []
for k, e in led.items():
    if e["status"] != "ahead" or k in now_ahead:
        continue
    r = itu.get((e["country"], e["mcc"], e["mnc"]))
    if r and r["status"] == "active":
        ev = [h for h in r["history"] if h["event"] in ("assigned", "reassigned", "amended_unbased")]
        h = ev[-1] if ev else r["history"][-1]
        e.update(status="published", itu_issue=h["issue"], itu_date=h["date"])
        e["gap_days"] = (datetime.date.fromisoformat(h["date"]) - datetime.date.fromisoformat(e["first_seen"])).days
    else:
        e.update(status="dropped", dropped_seen=today)
    changed.append((k, e["status"]))

json.dump(dict(sorted(led.items())), open(path, "w"), ensure_ascii=False, indent=1)
print(f"sightings: {sum(1 for e in led.values() if e['status']=='ahead')} ahead, "
      f"{sum(1 for e in led.values() if e['status']=='published')} published, "
      f"{sum(1 for e in led.values() if e['status']=='dropped')} dropped; changed this run: {changed}")
