"""Page through Traficom's approved-MNC e-service table (ASP.NET GridView postbacks).

Usage: python3 -I fetch_fi.py <first_page_html> <out_csv>
Fetches pages 2..N by posting the form state back, and writes all rows to CSV.
"""
import csv, html, re, sys, urllib.parse, urllib.request, http.cookiejar

URL = "https://eservices.traficom.fi/LicensesServices/Forms/NureMnctunnukset.aspx?langid=en"


def fields(t):
    out = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % name, t)
        if m:
            out[name] = html.unescape(m.group(1))
    return out


def rows(t):
    out = []
    for r in re.findall(r"<tr.*?</tr>", t, flags=re.S | re.I):
        cells = [html.unescape(re.sub(r"<.*?>", "", c)).strip() for c in re.findall(r"<t[dh].*?</t[dh]>", r, flags=re.S | re.I)]
        if len(cells) == 3 and re.fullmatch(r"\d{2,3}", cells[0]):
            out.append(cells)
    return out


def main(first, outp):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    t = op.open(URL, timeout=60).read().decode("utf-8", "replace")
    allrows = rows(t)
    pages = sorted({int(p) for p in re.findall(r"Page\$(\d+)", t)})
    print("page 1:", len(allrows), "| further pages:", pages)
    done = {1}
    while True:
        nxt = [p for p in sorted({int(p) for p in re.findall(r"Page\$(\d+)", t)}) if p not in done]
        if not nxt:
            break
        p = nxt[0]
        data = fields(t)
        data.update({"__EVENTTARGET": "NureMnctunnuksetGridView", "__EVENTARGUMENT": f"Page${p}"})
        t = op.open(URL, urllib.parse.urlencode(data).encode(), timeout=60).read().decode("utf-8", "replace")
        r = rows(t)
        print(f"page {p}:", len(r))
        allrows += r
        done.add(p)
    with open(outp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mnc", "company", "decision_date"])
        w.writerows(allrows)
    print("total rows:", len(allrows), "| distinct codes:", len({r[0] for r in allrows}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
